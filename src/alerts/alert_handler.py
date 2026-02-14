"""PriceMonitor用アラートハンドラー"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from loguru import logger

from alerts.alert_engine import AlertEngine
from database.db_manager import DatabaseManager


def _safe_float(value: Any) -> Optional[float]:
    """文字列や数値を安全にfloatに変換"""
    if value is None or value == "N/A":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """タイムスタンプを安全にdatetimeに変換"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # ISO形式
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass
    try:
        # Unix timestamp (ミリ秒)
        ts = float(value)
        if ts > 1e12:
            ts = ts / 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (ValueError, TypeError):
        return None


class AlertHandler:
    """PriceMonitorのadd_handlerに登録するハンドラー

    price_changeイベントを受信し、DB保存とアラート評価を行う。
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        alert_engine: AlertEngine,
    ):
        self.db = db_manager
        self.alert_engine = alert_engine

    async def handle_event(self, event_type: str, data: Dict[str, Any]):
        """PriceMonitorから呼ばれるイベントハンドラー

        Args:
            event_type: イベント種別
            data: イベントデータ
        """
        if event_type != "price_change":
            return

        asset_id = data.get("asset_id")
        if not asset_id:
            return

        market = data.get("market")
        price = _safe_float(data.get("price"))
        size = _safe_float(data.get("size"))
        best_bid = _safe_float(data.get("best_bid"))
        best_ask = _safe_float(data.get("best_ask"))
        timestamp = _parse_timestamp(data.get("timestamp"))

        # DB保存
        try:
            self.db.save_price(
                asset_id=asset_id,
                market=market,
                price=price,
                size=size,
                side=data.get("side"),
                best_bid=best_bid,
                best_ask=best_ask,
                timestamp=timestamp,
            )
        except Exception as e:
            logger.error(f"価格データDB保存エラー: {e}")

        # アラート評価
        if price is not None:
            try:
                await self.alert_engine.check_alerts(
                    asset_id=asset_id,
                    market=market,
                    price=price,
                    size=size,
                )
            except Exception as e:
                logger.error(f"アラート評価エラー: {e}")
