"""ConditionCheckerのユニットテスト"""
from datetime import datetime, timedelta, timezone

import pytest

from alerts.conditions import ConditionChecker
from database.db_manager import DatabaseManager


class TestConditionChecker:
    @pytest.fixture
    def db_manager(self):
        return DatabaseManager(db_path=":memory:")

    @pytest.fixture
    def checker(self, db_manager):
        return ConditionChecker(db_manager)

    def test_price_below_true(self, checker):
        """価格が閾値を下回る場合Trueを返す"""
        assert checker.check_price_below(0.05, 0.10) is True

    def test_price_below_false(self, checker):
        """価格が閾値以上の場合Falseを返す"""
        assert checker.check_price_below(0.15, 0.10) is False

    def test_price_below_equal(self, checker):
        """価格が閾値と等しい場合Falseを返す"""
        assert checker.check_price_below(0.10, 0.10) is False

    def test_price_above_true(self, checker):
        """価格が閾値を上回る場合Trueを返す"""
        assert checker.check_price_above(0.95, 0.90) is True

    def test_price_above_false(self, checker):
        """価格が閾値以下の場合Falseを返す"""
        assert checker.check_price_above(0.85, 0.90) is False

    def test_price_above_equal(self, checker):
        """価格が閾値と等しい場合Falseを返す"""
        assert checker.check_price_above(0.90, 0.90) is False

    def test_volume_above_true(self, checker):
        """取引量が閾値を上回る場合Trueを返す"""
        assert checker.check_volume_above(1500.0, 1000.0) is True

    def test_volume_above_false(self, checker):
        """取引量が閾値以下の場合Falseを返す"""
        assert checker.check_volume_above(500.0, 1000.0) is False

    def test_price_change_percent_no_history(self, checker):
        """履歴がない場合Falseを返す"""
        result = checker.check_price_change_percent(
            market="0xtest", current_price=0.50,
            timeframe_minutes=5, threshold_percent=10.0,
        )
        assert result is False

    def test_price_change_percent_up(self, db_manager, checker):
        """価格上昇率が閾値を超える場合Trueを返す"""
        # 5分前の価格を挿入
        old_time = datetime.now(timezone.utc) - timedelta(minutes=3)
        db_manager.save_price(
            asset_id="token1", market="0xtest",
            price=0.50, timestamp=old_time,
        )
        result = checker.check_price_change_percent(
            market="0xtest", current_price=0.60,
            timeframe_minutes=5, threshold_percent=10.0,
        )
        assert result is True  # 20% > 10%

    def test_price_change_percent_down(self, db_manager, checker):
        """価格下落率が閾値を超える場合Trueを返す"""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=3)
        db_manager.save_price(
            asset_id="token1", market="0xtest",
            price=0.50, timestamp=old_time,
        )
        result = checker.check_price_change_percent(
            market="0xtest", current_price=0.40,
            timeframe_minutes=5, threshold_percent=-10.0,
        )
        assert result is True  # -20% <= -10%

    def test_price_change_percent_not_enough(self, db_manager, checker):
        """価格変動が閾値に達しない場合Falseを返す"""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=3)
        db_manager.save_price(
            asset_id="token1", market="0xtest",
            price=0.50, timestamp=old_time,
        )
        result = checker.check_price_change_percent(
            market="0xtest", current_price=0.52,
            timeframe_minutes=5, threshold_percent=10.0,
        )
        assert result is False  # 4% < 10%
