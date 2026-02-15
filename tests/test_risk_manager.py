"""RiskManager テスト"""
from datetime import datetime, timedelta, timezone

import pytest

from database.db_manager import DatabaseManager
from executor.position_manager import PositionManager
from risk.risk_manager import RiskManager

DEFAULT_CONFIG = {
    "global": {
        "max_total_position_usdc": 1000,
        "max_daily_loss_usdc": 100,
        "max_daily_trades": 50,
        "max_single_trade_usdc": 100,
    },
    "circuit_breaker": {
        "enabled": True,
        "cooldown_minutes": 60,
    },
}


@pytest.fixture
def db():
    return DatabaseManager(db_path=":memory:")


@pytest.fixture
def pm(db):
    return PositionManager(db)


@pytest.fixture
def rm(db, pm):
    return RiskManager(DEFAULT_CONFIG, db, pm)


class TestOrderApproval:
    """制限内の注文が通ること"""

    def test_normal_buy_approved(self, rm):
        assert rm.check_order("asset1", "BUY", 50.0) is True

    def test_normal_sell_approved(self, rm):
        assert rm.check_order("asset1", "SELL", 50.0) is True


class TestSingleTradeLimit:
    """単一取引サイズ超過で拒否"""

    def test_exceeds_single_trade_limit(self, rm):
        assert rm.check_order("asset1", "BUY", 150.0) is False

    def test_at_limit(self, rm):
        assert rm.check_order("asset1", "BUY", 100.0) is True


class TestPositionLimit:
    """最大ポジション上限テスト"""

    def test_exceeds_total_position(self, db, pm):
        rm = RiskManager(
            {
                "global": {
                    "max_total_position_usdc": 200,
                    "max_daily_loss_usdc": 100,
                    "max_daily_trades": 50,
                    "max_single_trade_usdc": 200,
                },
                "circuit_breaker": {"enabled": True, "cooldown_minutes": 60},
            },
            db,
            pm,
        )
        pm.update_after_trade("a1", "m", "BUY", 0.50, 150.0)
        # 150 + 100 = 250 > 200
        assert rm.check_order("a2", "BUY", 100.0) is False

    def test_sell_not_checked_for_position_limit(self, db, pm):
        rm = RiskManager(
            {
                "global": {
                    "max_total_position_usdc": 200,
                    "max_daily_loss_usdc": 100,
                    "max_daily_trades": 50,
                    "max_single_trade_usdc": 200,
                },
                "circuit_breaker": {"enabled": True, "cooldown_minutes": 60},
            },
            db,
            pm,
        )
        pm.update_after_trade("a1", "m", "BUY", 0.50, 200.0)
        # SELL は position limit チェックしない
        assert rm.check_order("a1", "SELL", 100.0) is True


class TestDailyTradeLimit:
    """日次取引回数上限テスト"""

    def test_exceeds_daily_trades(self, db, pm):
        rm = RiskManager(
            {
                "global": {
                    "max_total_position_usdc": 100000,
                    "max_daily_loss_usdc": 100000,
                    "max_daily_trades": 3,
                    "max_single_trade_usdc": 100,
                },
                "circuit_breaker": {"enabled": True, "cooldown_minutes": 60},
            },
            db,
            pm,
        )
        # 3件の取引を記録
        for i in range(3):
            db.save_trade(f"a{i}", "m", "BUY", 0.50, 10.0)

        assert rm.check_order("a3", "BUY", 10.0) is False


class TestCircuitBreaker:
    """サーキットブレーカーテスト"""

    def test_triggered_by_daily_loss(self, db, pm):
        rm = RiskManager(
            {
                "global": {
                    "max_total_position_usdc": 100000,
                    "max_daily_loss_usdc": 50,
                    "max_daily_trades": 100,
                    "max_single_trade_usdc": 1000,
                },
                "circuit_breaker": {"enabled": True, "cooldown_minutes": 60},
            },
            db,
            pm,
        )
        # 大きな損失を記録
        db.save_trade("a", "m", "SELL", 0.40, 100.0, realized_pnl=-60.0)

        assert rm.check_order("a", "BUY", 10.0) is False
        # サーキットブレーカーが発動しているので次の注文も拒否
        assert rm.check_order("a2", "BUY", 10.0) is False

    def test_auto_recovery(self, db, pm):
        rm = RiskManager(
            {
                "global": {
                    "max_total_position_usdc": 100000,
                    "max_daily_loss_usdc": 100000,
                    "max_daily_trades": 100,
                    "max_single_trade_usdc": 100,
                },
                "circuit_breaker": {"enabled": True, "cooldown_minutes": 60},
            },
            db,
            pm,
        )
        # 手動でサーキットブレーカーを発動
        rm._trigger_circuit_breaker()
        assert rm.check_order("a", "BUY", 10.0) is False

        # クールダウン経過をシミュレート
        rm._halted_at = datetime.now(timezone.utc) - timedelta(minutes=61)
        assert rm.check_order("a", "BUY", 10.0) is True
        assert rm._halted is False
