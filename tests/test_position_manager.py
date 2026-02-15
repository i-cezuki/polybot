"""PositionManager テスト"""
import pytest

from database.db_manager import DatabaseManager
from executor.position_manager import PositionManager


@pytest.fixture
def db():
    return DatabaseManager(db_path=":memory:")


@pytest.fixture
def pm(db):
    return PositionManager(db)


class TestNewPosition:
    """新規ポジション作成テスト"""

    def test_buy_creates_position(self, pm, db):
        pnl = pm.update_after_trade("asset1", "market1", "BUY", 0.50, 10.0)
        assert pnl == 0.0
        pos = pm.get_position("asset1")
        assert pos is not None
        assert pos.size_usdc == 10.0
        assert pos.average_price == 0.50

    def test_get_position_usdc_no_position(self, pm):
        assert pm.get_position_usdc("nonexistent") == 0.0

    def test_get_position_usdc_after_buy(self, pm):
        pm.update_after_trade("asset1", "market1", "BUY", 0.50, 20.0)
        assert pm.get_position_usdc("asset1") == 20.0


class TestPositionAdd:
    """ポジション加算（加重平均）テスト"""

    def test_weighted_average_price(self, pm):
        pm.update_after_trade("asset1", "market1", "BUY", 0.40, 10.0)
        pm.update_after_trade("asset1", "market1", "BUY", 0.60, 10.0)
        pos = pm.get_position("asset1")
        assert pos.size_usdc == 20.0
        assert pos.average_price == pytest.approx(0.50, abs=0.001)

    def test_multiple_adds(self, pm):
        pm.update_after_trade("a", "m", "BUY", 0.30, 30.0)
        pm.update_after_trade("a", "m", "BUY", 0.60, 30.0)
        pm.update_after_trade("a", "m", "BUY", 0.90, 30.0)
        pos = pm.get_position("a")
        assert pos.size_usdc == 90.0
        expected_avg = (0.30 * 30 + 0.60 * 30 + 0.90 * 30) / 90
        assert pos.average_price == pytest.approx(expected_avg, abs=0.001)


class TestPartialClose:
    """部分決済テスト"""

    def test_partial_sell_reduces_position(self, pm):
        pm.update_after_trade("a", "m", "BUY", 0.50, 100.0)
        pm.update_after_trade("a", "m", "SELL", 0.60, 50.0)
        pos = pm.get_position("a")
        assert pos is not None
        assert pos.size_usdc == 50.0
        assert pos.average_price == 0.50  # avg unchanged on partial sell


class TestFullClose:
    """全決済テスト"""

    def test_full_sell_removes_position(self, pm):
        pm.update_after_trade("a", "m", "BUY", 0.50, 100.0)
        pm.update_after_trade("a", "m", "SELL", 0.60, 100.0)
        pos = pm.get_position("a")
        assert pos is None

    def test_oversell_capped_to_position(self, pm):
        pm.update_after_trade("a", "m", "BUY", 0.50, 50.0)
        pnl = pm.update_after_trade("a", "m", "SELL", 0.60, 100.0)
        # sell is capped to 50
        pos = pm.get_position("a")
        assert pos is None
        assert pnl != 0.0


class TestPnLCalculation:
    """P&L 計算テスト"""

    def test_profit_on_sell(self, pm):
        pm.update_after_trade("a", "m", "BUY", 0.50, 100.0)
        pnl = pm.update_after_trade("a", "m", "SELL", 0.60, 100.0)
        # pnl = 100 * (0.60 - 0.50) / 0.50 = 20.0
        assert pnl == pytest.approx(20.0, abs=0.01)

    def test_loss_on_sell(self, pm):
        pm.update_after_trade("a", "m", "BUY", 0.50, 100.0)
        pnl = pm.update_after_trade("a", "m", "SELL", 0.40, 100.0)
        # pnl = 100 * (0.40 - 0.50) / 0.50 = -20.0
        assert pnl == pytest.approx(-20.0, abs=0.01)

    def test_partial_sell_pnl(self, pm):
        pm.update_after_trade("a", "m", "BUY", 0.50, 100.0)
        pnl = pm.update_after_trade("a", "m", "SELL", 0.60, 50.0)
        # pnl = 50 * (0.60 - 0.50) / 0.50 = 10.0
        assert pnl == pytest.approx(10.0, abs=0.01)

    def test_sell_without_position_returns_zero(self, pm):
        pnl = pm.update_after_trade("a", "m", "SELL", 0.60, 50.0)
        assert pnl == 0.0


class TestTotalPosition:
    """合計ポジションテスト"""

    def test_total_across_assets(self, pm):
        pm.update_after_trade("a1", "m", "BUY", 0.50, 100.0)
        pm.update_after_trade("a2", "m", "BUY", 0.60, 200.0)
        assert pm.get_total_position_usdc() == 300.0

    def test_total_empty(self, pm):
        assert pm.get_total_position_usdc() == 0.0
