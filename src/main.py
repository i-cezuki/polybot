"""メインエントリーポイント"""
import asyncio
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


async def main():
    """メイン処理"""

    # ロガー初期化
    setup_logger("INFO")
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

        # 監視対象マーケットのトークンID収集
        enabled_markets = [
            m for m in markets_config["markets"] if m.get("enabled", True)
        ]
        logger.info(f"監視対象マーケット数: {len(enabled_markets)}")

        all_token_ids = []

        for market in enabled_markets:
            condition_id = market["market_id"]
            market_name = market.get("name", "N/A")

            # Gamma APIでマーケット情報取得
            market_info = await poly_client.get_market_by_condition_id(condition_id)

            if market_info:
                question = market_info.get("question", "N/A")
                outcomes = market_info.get("outcomes", "N/A")
                outcome_prices = market_info.get("outcomePrices", "N/A")

                logger.info(
                    f"マーケット: {market_name} | "
                    f"質問: {question} | "
                    f"outcomes: {outcomes} | "
                    f"prices: {outcome_prices}"
                )

                # CLOBトークンIDを取得
                clob_token_ids = market_info.get("clobTokenIds")
                if clob_token_ids:
                    if isinstance(clob_token_ids, str):
                        # カンマ区切りの場合
                        token_ids = [
                            tid.strip() for tid in clob_token_ids.split(",")
                        ]
                    elif isinstance(clob_token_ids, list):
                        token_ids = clob_token_ids
                    else:
                        token_ids = []

                    all_token_ids.extend(token_ids)
                    logger.info(f"トークンID: {token_ids}")

                    # REST APIで現在価格を取得
                    for token_id in token_ids:
                        midpoint = await poly_client.get_midpoint(token_id)
                        if midpoint is not None:
                            logger.info(
                                f"現在のミッドポイント: token={token_id[:16]}... price={midpoint}"
                            )
            else:
                logger.warning(f"マーケット情報取得失敗: {market_name} ({condition_id})")

        if not all_token_ids:
            logger.warning(
                "購読対象のトークンIDがありません。"
                "config/markets.yamlの market_id を実際のcondition IDに更新してください。"
            )
            logger.info("WebSocket接続をスキップします。")

            # トークンIDがなくてもGamma APIのテストとして動作確認
            logger.info("--- Gamma APIテスト: アクティブマーケット一覧取得 ---")
            active_markets = await poly_client.get_markets_from_gamma(limit=5)
            for m in active_markets:
                logger.info(
                    f"  [{m.get('id', 'N/A')[:8]}...] {m.get('question', 'N/A')}"
                )

            return

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
