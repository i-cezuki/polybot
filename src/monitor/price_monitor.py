"""価格監視モジュール"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from loguru import logger


class PriceMonitor:
    """価格監視クラス（Polymarket CLOB WebSocketイベント対応）"""

    def __init__(self):
        self.price_data: Dict[str, Dict[str, Any]] = {}
        self.orderbooks: Dict[str, Dict[str, Any]] = {}
        logger.info("PriceMonitor 初期化完了")

    async def on_price_update(self, data: Union[Dict, List, Any]):
        """WebSocketメッセージ受信時のコールバック"""
        try:
            if isinstance(data, list):
                # bookイベント等: [{event_type: "book", ...}, ...]
                for item in data:
                    if isinstance(item, dict):
                        await self._process_event(item)
            elif isinstance(data, dict):
                await self._process_event(data)
        except Exception as e:
            logger.error(f"価格更新処理エラー: {e} | data={str(data)[:200]}", exc_info=True)

    async def _process_event(self, data: Dict[str, Any]):
        """単一イベントを処理"""
        try:
            event_type = data.get("event_type")

            if event_type == "book":
                await self._handle_book(data)
            elif event_type == "last_trade_price":
                await self._handle_last_trade(data)
            elif event_type == "tick_size_change":
                await self._handle_tick_size_change(data)
            elif "price_changes" in data:
                # ラッパー形式: {"market": "...", "price_changes": [...]}
                market = data.get("market", "")
                for change in data["price_changes"]:
                    if isinstance(change, dict):
                        change["market"] = market
                        await self._handle_price_change(change)
            elif event_type == "price_change":
                await self._handle_price_change(data)
            else:
                logger.debug(f"未処理イベント: keys={list(data.keys())}")
        except Exception as e:
            logger.error(
                f"イベント処理エラー: {e} | keys={list(data.keys())} | data={str(data)[:300]}",
                exc_info=True,
            )

    def _short_id(self, asset_id: Optional[str]) -> str:
        if not asset_id:
            return "unknown"
        return asset_id[:16] + "..."

    async def _handle_book(self, data: Dict[str, Any]):
        """オーダーブックスナップショット処理"""
        asset_id = data.get("asset_id")
        if not asset_id:
            return

        market = data.get("market")
        timestamp = data.get("timestamp")
        bids = data.get("bids") or []
        asks = data.get("asks") or []

        self.orderbooks[asset_id] = {
            "bids": bids,
            "asks": asks,
            "timestamp": timestamp,
            "market": market,
        }

        best_bid = "N/A"
        best_ask = "N/A"
        if bids and isinstance(bids[0], dict):
            best_bid = bids[0].get("price", "N/A")
        if asks and isinstance(asks[0], dict):
            best_ask = asks[0].get("price", "N/A")

        logger.info(
            f"[BOOK] asset={self._short_id(asset_id)} | "
            f"best_bid={best_bid} | best_ask={best_ask} | "
            f"bids={len(bids)} | asks={len(asks)}"
        )

    async def _handle_price_change(self, data: Dict[str, Any]):
        """価格変更イベント処理"""
        asset_id = data.get("asset_id")
        if not asset_id:
            return

        price = data.get("price")
        size = data.get("size")
        side = data.get("side")
        best_bid = data.get("best_bid")
        best_ask = data.get("best_ask")
        timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())

        self.price_data[asset_id] = {
            "price": price,
            "size": size,
            "side": side,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "timestamp": timestamp,
        }

        logger.info(
            f"[PRICE] asset={self._short_id(asset_id)} | "
            f"side={side} | price={price} | size={size} | "
            f"bid={best_bid} | ask={best_ask}"
        )

    async def _handle_last_trade(self, data: Dict[str, Any]):
        """最終取引価格イベント処理"""
        asset_id = data.get("asset_id")
        price = data.get("price")
        size = data.get("size")
        side = data.get("side")

        logger.info(
            f"[TRADE] asset={self._short_id(asset_id)} | "
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
        """現在価格を取得"""
        if asset_id in self.price_data:
            return float(self.price_data[asset_id]["price"])
        return None

    def get_orderbook(self, asset_id: str) -> Optional[Dict[str, Any]]:
        """現在のオーダーブックを取得"""
        return self.orderbooks.get(asset_id)
