"""アラートエンジン"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from loguru import logger

from alerts.conditions import ConditionChecker
from database.db_manager import DatabaseManager
from notifications.notification_manager import NotificationManager


class AlertEngine:
    """アラート評価エンジン

    alerts.yamlの定義に基づき、価格イベントを受信するたびに
    条件をチェックし、成立時にアラートを発火する。
    """

    def __init__(
        self,
        alerts_config: dict,
        db_manager: DatabaseManager,
        notification_manager: NotificationManager,
    ):
        self.alerts = alerts_config.get("alerts", [])
        self.db = db_manager
        self.notifier = notification_manager
        self.condition_checker = ConditionChecker(db_manager)
        logger.info(f"アラートエンジン初期化: {len(self.alerts)} 件のアラート")

    async def check_alerts(
        self,
        asset_id: str,
        market: Optional[str],
        price: float,
        size: Optional[float] = None,
    ):
        """全アラートルールを評価"""
        for alert in self.alerts:
            alert_market_id = alert.get("market_id", "*")

            # マーケットマッチング
            if alert_market_id != "*" and alert_market_id != market:
                continue

            try:
                await self._evaluate_alert(alert, asset_id, market, price, size)
            except Exception as e:
                logger.error(f"アラート評価エラー ({alert.get('name')}): {e}")

    async def _evaluate_alert(
        self,
        alert: dict,
        asset_id: str,
        market: Optional[str],
        price: float,
        size: Optional[float],
    ):
        """個別アラートルールを評価"""
        alert_name = alert.get("name", "unnamed")
        match_mode = alert.get("match_mode", "match_any")
        cooldown_minutes = alert.get("cooldown_minutes", 10)
        conditions = alert.get("conditions", [])

        if not conditions:
            return

        # クールダウンチェック
        if self._is_in_cooldown(alert_name, cooldown_minutes):
            return

        # 条件評価
        results = []
        triggered_condition = None
        triggered_value = None

        for cond in conditions:
            cond_type = cond.get("type")
            matched = False

            if cond_type == "price_below":
                matched = self.condition_checker.check_price_below(
                    price, cond["threshold"]
                )
                if matched:
                    triggered_condition = cond_type
                    triggered_value = price

            elif cond_type == "price_above":
                matched = self.condition_checker.check_price_above(
                    price, cond["threshold"]
                )
                if matched:
                    triggered_condition = cond_type
                    triggered_value = price

            elif cond_type == "price_change_percent":
                if market:
                    matched = self.condition_checker.check_price_change_percent(
                        market=market,
                        current_price=price,
                        timeframe_minutes=cond.get("timeframe_minutes", 5),
                        threshold_percent=cond["threshold_percent"],
                    )
                    if matched:
                        triggered_condition = cond_type
                        triggered_value = price

            elif cond_type == "volume_above":
                if size is not None:
                    matched = self.condition_checker.check_volume_above(
                        size, cond["threshold"]
                    )
                    if matched:
                        triggered_condition = cond_type
                        triggered_value = size

            results.append(matched)

        # match_mode に基づき判定
        if match_mode == "match_all":
            should_trigger = all(results) and any(results)
        else:  # match_any
            should_trigger = any(results)

        if should_trigger and triggered_condition is not None:
            # トリガーした条件の threshold を取得
            threshold = self._get_threshold(conditions, triggered_condition)
            await self._trigger_alert(
                alert_name=alert_name,
                asset_id=asset_id,
                market=market,
                condition_type=triggered_condition,
                threshold=threshold,
                current_value=triggered_value,
                price=price,
            )

    def _get_threshold(self, conditions: list, condition_type: str) -> float:
        """条件リストから該当条件の閾値を取得"""
        for cond in conditions:
            if cond.get("type") == condition_type:
                if condition_type == "price_change_percent":
                    return cond.get("threshold_percent", 0.0)
                return cond.get("threshold", 0.0)
        return 0.0

    def _is_in_cooldown(self, alert_name: str, cooldown_minutes: int) -> bool:
        """クールダウン期間内かチェック"""
        last_time = self.db.get_last_alert_time(alert_name)
        if last_time is None:
            return False

        # naive datetime の場合 UTC として扱う
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)

        cooldown_until = last_time + timedelta(minutes=cooldown_minutes)
        return datetime.now(timezone.utc) < cooldown_until

    async def _trigger_alert(
        self,
        alert_name: str,
        asset_id: str,
        market: Optional[str],
        condition_type: str,
        threshold: float,
        current_value: float,
        price: float,
    ):
        """アラートを発火: DB保存 + 通知送信"""
        message = (
            f"アラート '{alert_name}' 発火: "
            f"{condition_type} (閾値={threshold}, 現在値={current_value})"
        )
        logger.warning(f"[ALERT] {message} | asset={asset_id[:16]}...")

        # DB保存
        alert_log_id = self.db.save_alert_log(
            alert_name=alert_name,
            asset_id=asset_id,
            condition_type=condition_type,
            threshold=threshold,
            current_value=current_value,
            message=message,
        )

        # 通知送信
        market_name = market or asset_id[:16]
        await self.notifier.send_alert(
            alert_log_id=alert_log_id,
            market_name=market_name,
            price=str(price),
            condition=condition_type,
            message=message,
        )
