"""価格監視モジュール"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from loguru import logger


class PriceMonitor:
    """価格監視クラス（Polymarket CLOB WebSocketイベント対応）"""

    def __init__(self):
        self.price_data: Dict[str, Dict[str, Any]] = {}
        self.orderbooks: Dict[str, Dict[str, Any]] = {}
        logger.info("PriceMonitor 初期化完了")

    async def on_price_update(self, data):
        """
        WebSocketメッセージ受信時のコールバック

        Polymarket CLOB WebSocketのイベントタイプ:
        - book: オーダーブックスナップショット
        - price_change: 価格レベル更新
        - last_trade_price: 最終取引価格
        - tick_size_change: ティックサイズ変更

        Args:
            data: WebSocketから受信したデータ（dictまたはlist）
        """
        try:
            # メッセージがリストの場合、各要素を個別処理
            if isinstance(data, list):
                for item in data:
                    await self._process_event(item)
            elif isinstance(data, dict):
                await self._process_event(data)
            else:
                logger.debug(f"未知のデータ形式: type={type(data)}, data={data}")

        except Exception as e:
            logger.error(f"価格更新処理エラー: {e}")

    async def _process_event(self, data: Dict[str, Any]):
        """単一イベントを処理"""
        event_type = data.get("event_type")

        if event_type == "book":
            await self._handle_book(data)
        elif event_type == "price_change":
            await self._handle_price_change(data)
        elif event_type == "last_trade_price":
            await self._handle_last_trade(data)
        elif event_type == "tick_size_change":
            await self._handle_tick_size_change(data)
        else:
            logger.debug(f"未処理イベント: {event_type}, data={data}")

    async def _handle_book(self, data: Dict[str, Any]):
        """オーダーブックスナップショット処理"""
        asset_id = data.get("asset_id")
        market = data.get("market")
        timestamp = data.get("timestamp")
        buys = data.get("buys", [])
        sells = data.get("sells", [])

        self.orderbooks[asset_id] = {
            "buys": buys,
            "sells": sells,
            "timestamp": timestamp,
            "market": market,
        }

        best_bid = buys[0]["price"] if buys else "N/A"
        best_ask = sells[0]["price"] if sells else "N/A"

        logger.info(
            f"[BOOK] asset={asset_id[:16]}... | "
            f"best_bid={best_bid} | best_ask={best_ask} | "
            f"bids={len(buys)} | asks={len(sells)}"
        )

    async def _handle_price_change(self, data: Dict[str, Any]):
        """価格変更イベント処理"""
        asset_id = data.get("asset_id")
        price = data.get("price")
        size = data.get("size")
        side = data.get("side")
        timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())

        self.price_data[asset_id] = {
            "price": price,
            "size": size,
            "side": side,
            "timestamp": timestamp,
        }

        logger.info(
            f"[PRICE] asset={asset_id[:16]}... | "
            f"side={side} | price={price} | size={size}"
        )

    async def _handle_last_trade(self, data: Dict[str, Any]):
        """最終取引価格イベント処理"""
        asset_id = data.get("asset_id")
        price = data.get("price")
        size = data.get("size")
        side = data.get("side")

        logger.info(
            f"[TRADE] asset={asset_id[:16]}... | "
            f"side={side} | price={price} | size={size}"
        )

    async def _handle_tick_size_change(self, data: Dict[str, Any]):
        """ティックサイズ変更イベント処理"""
        old_tick = data.get("old_tick_size")
        new_tick = data.get("new_tick_size")
        side = data.get("side")

        logger.info(
            f"[TICK] tick_size変更: {old_tick} -> {new_tick} | side={side}"
        )

    def get_current_price(self, asset_id: str) -> Optional[float]:
        """
        現在価格を取得

        Args:
            asset_id: アセットID

        Returns:
            float: 現在価格
        """
        if asset_id in self.price_data:
            return float(self.price_data[asset_id]["price"])
        logger.warning(f"価格データが存在しません: {asset_id}")
        return None

    def get_orderbook(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """
        現在のオーダーブックを取得

        Args:
            asset_id: アセットID

        Returns:
            Dict: オーダーブック
        """
        return self.orderbooks.get(asset_id)
