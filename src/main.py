"""メインエントリーポイント"""
import asyncio
import json
import sys
from pathlib import Path

# srcディレクトリをパスに追加（Dockerとローカル両方対応）
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger

from api.polymarket_client import PolymarketClient
from api.websocket_client import WebSocketClient
from monitor.price_monitor import PriceMonitor
from utils.config_loader import ConfigLoader
from utils.logger import setup_logger


def extract_token_ids(market_info: dict) -> list[str]:
    """マーケット情報からCLOBトークンIDを抽出する"""
    clob_token_ids = market_info.get("clobTokenIds")
    if not clob_token_ids:
        return []

    if isinstance(clob_token_ids, str):
        try:
            return json.loads(clob_token_ids)
        except json.JSONDecodeError:
            return [clob_token_ids]
    elif isinstance(clob_token_ids, list):
        return clob_token_ids
    return []


def is_market_active(market_info: dict) -> bool:
    """マーケットがアクティブ（未解決）かどうか判定する"""
    # active フラグ
    if not market_info.get("active", True):
        return False
    # closed フラグ
    if market_info.get("closed", False):
        return False
    # 価格が 0 or 1 のみの場合は解決済み
    prices_raw = market_info.get("outcomePrices", "")
    if prices_raw:
        try:
            prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
            if all(float(p) in (0.0, 1.0) for p in prices):
                return False
        except (json.JSONDecodeError, ValueError):
            pass
    return True


async def collect_markets_auto(poly_client: PolymarketClient, limit: int) -> list[dict]:
    """Gamma APIからアクティブなマーケットを自動取得する"""
    logger.info(f"Gamma APIからアクティブなマーケットを自動取得中 (上限: {limit}件)...")
    gamma_markets = await poly_client.get_markets_from_gamma(
        active=True, closed=False, limit=limit * 3,  # 余裕を持って取得
    )

    active_markets = []
    for m in gamma_markets:
        if not is_market_active(m):
            continue
        token_ids = extract_token_ids(m)
        if not token_ids:
            continue
        active_markets.append(m)
        if len(active_markets) >= limit:
            break

    return active_markets


async def collect_markets_manual(
    poly_client: PolymarketClient, markets_config: list[dict]
) -> list[dict]:
    """markets.yaml の手動指定からマーケット情報を取得する"""
    enabled = [m for m in markets_config if m.get("enabled", True)]
    logger.info(f"設定ファイルから {len(enabled)} 件のマーケットを読み込み")

    result = []
    for market in enabled:
        condition_id = market["market_id"]
        market_info = await poly_client.get_market_by_condition_id(condition_id)
        if market_info and is_market_active(market_info):
            result.append(market_info)
        else:
            name = market.get("name", condition_id)
            logger.warning(f"スキップ（見つからないか解決済み）: {name}")
    return result


async def main():
    """メイン処理"""

    # ロガー初期化
    setup_logger("DEBUG")
    logger.info("=== PolyBot Framework 起動 ===")

    ws_client = None
    poly_client = None

    try:
        # 設定読み込み
        config_loader = ConfigLoader()
        config = config_loader.load_yaml("config.yaml")
        markets_config = config_loader.load_yaml("markets.yaml")
        api_credentials = config_loader.get_api_credentials()

        logger.info("設定ファイル読み込み完了")

        # Polymarket クライアント初期化
        poly_client = PolymarketClient(
            api_key=api_credentials["POLYMARKET_API_KEY"],
            api_secret=api_credentials["POLYMARKET_API_SECRET"],
            api_passphrase=api_credentials["POLYMARKET_API_PASSPHRASE"],
            private_key=api_credentials["POLYMARKET_PRIVATE_KEY"],
            funder_address=api_credentials["POLYMARKET_FUNDER_ADDRESS"],
        )

        # CLOB API接続確認
        is_connected = await poly_client.check_connection()
        if not is_connected:
            logger.error("CLOB APIへの接続に失敗しました。終了します。")
            return

        server_time = await poly_client.get_server_time()
        logger.info(f"サーバー時刻: {server_time}")

        # 価格モニター初期化
        price_monitor = PriceMonitor()

        # マーケット取得（自動 or 手動）
        auto_discover = markets_config.get("auto_discover", False)
        if auto_discover:
            limit = markets_config.get("auto_discover_limit", 3)
            target_markets = await collect_markets_auto(poly_client, limit)
        else:
            target_markets = await collect_markets_manual(
                poly_client, markets_config.get("markets", [])
            )

        if not target_markets:
            logger.error("監視対象のアクティブなマーケットが見つかりません。終了します。")
            return

        # トークンID収集 & マーケット情報ログ出力
        all_token_ids = []
        for market_info in target_markets:
            question = market_info.get("question", "N/A")
            outcomes = market_info.get("outcomes", "N/A")
            outcome_prices = market_info.get("outcomePrices", "N/A")
            condition_id = market_info.get("conditionId", "N/A")

            logger.info(
                f"監視対象: {question} | "
                f"outcomes: {outcomes} | "
                f"prices: {outcome_prices}"
            )

            token_ids = extract_token_ids(market_info)
            all_token_ids.extend(token_ids)
            logger.info(f"  トークンID: {[tid[:16] + '...' for tid in token_ids]}")

            # REST APIで現在のミッドポイント価格を取得
            for token_id in token_ids:
                midpoint = await poly_client.get_midpoint(token_id)
                if midpoint is not None:
                    logger.info(f"  ミッドポイント: {token_id[:16]}... = {midpoint}")

        logger.info(f"合計 {len(target_markets)} マーケット / {len(all_token_ids)} トークンを監視")

        # WebSocket接続
        ws_url = config["polymarket"]["api"]["websocket"]
        ws_client = WebSocketClient(
            ws_url=ws_url,
            on_message=price_monitor.on_price_update,
            reconnect_delay=config["monitoring"]["reconnect_delay_seconds"],
            max_reconnect_attempts=config["monitoring"]["max_reconnect_attempts"],
        )

        await ws_client.connect()

        # トークンIDで購読
        await ws_client.subscribe_to_market(all_token_ids)

        logger.info("価格監視開始...")

        # メッセージ受信ループ
        await ws_client.listen()

    except KeyboardInterrupt:
        logger.info("プログラムを終了します...")
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}", exc_info=True)
    finally:
        if ws_client:
            await ws_client.close()
        if poly_client:
            await poly_client.close()
        logger.info("=== PolyBot Framework 終了 ===")


if __name__ == "__main__":
    asyncio.run(main())
