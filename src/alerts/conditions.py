"""アラート条件チェッカー"""
from loguru import logger

from database.db_manager import DatabaseManager


class ConditionChecker:
    """各種アラート条件を評価するクラス"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def check_price_below(self, current_price: float, threshold: float) -> bool:
        """価格が閾値を下回っているか"""
        return current_price < threshold

    def check_price_above(self, current_price: float, threshold: float) -> bool:
        """価格が閾値を上回っているか"""
        return current_price > threshold

    def check_price_change_percent(
        self,
        market: str,
        current_price: float,
        timeframe_minutes: int,
        threshold_percent: float,
    ) -> bool:
        """指定期間内の価格変動率が閾値を超えているか

        threshold_percent が正の場合は上昇率、負の場合は下落率をチェック。
        """
        history = self.db.get_price_history(market=market, minutes=timeframe_minutes)
        if not history:
            return False

        oldest_price = history[0].price
        if not oldest_price or oldest_price == 0:
            return False

        change_percent = ((current_price - oldest_price) / oldest_price) * 100

        if threshold_percent > 0:
            return change_percent >= threshold_percent
        else:
            return change_percent <= threshold_percent

    def check_volume_above(self, current_volume: float, threshold: float) -> bool:
        """取引量が閾値を上回っているか"""
        return current_volume > threshold
