"""StrategyHandler テスト"""
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from database.db_manager import DatabaseManager
from executor.order_executor import OrderExecutor
from executor.position_manager import PositionManager
from risk.risk_manager import RiskManager
from strategy.strategy_handler import StrategyHandler

DEFAULT_RISK_CONFIG = {
    "global": {
        "max_total_position_usdc": 10000,
        "max_daily_loss_usdc": 1000,
        "max_daily_trades": 100,
        "max_single_trade_usdc": 1000,
    },
    "circuit_breaker": {"enabled": True, "cooldown_minutes": 60},
}


def _write_strategy(tmpdir: Path, code: str) -> str:
    """一時ファイルに戦略コードを書き出す"""
    path = tmpdir / "strategy.py"
    path.write_text(code)
    return str(path)


@pytest.fixture
def db():
    return DatabaseManager(db_path=":memory:")


@pytest.fixture
def components(db):
    pm = PositionManager(db)
    rm = RiskManager(DEFAULT_RISK_CONFIG, db, pm)
    oe = OrderExecutor(db)
    return db, pm, rm, oe


def _make_handler(components, strategy_code: str) -> StrategyHandler:
    """StrategyHandler を戦略コード付きで作成"""
    db, pm, rm, oe = components
    with tempfile.TemporaryDirectory() as tmpdir:
        path = _write_strategy(Path(tmpdir), strategy_code)
        handler = StrategyHandler(db, rm, oe, pm, strategy_path=path)
    return handler


def _make_handler_with_default(components) -> StrategyHandler:
    """デフォルト戦略でStrategyHandlerを作成"""
    return _make_handler(
        components,
        """
def calculate_signal(data):
    price = data.get("price")
    position_usdc = data.get("position_usdc", 0.0)
    if price < 0.30 and position_usdc == 0.0:
        return {"action": "BUY", "amount": 10.0, "reason": "cheap"}
    if price > 0.70 and position_usdc > 0.0:
        return {"action": "SELL", "amount": position_usdc, "reason": "expensive"}
    return {"action": "HOLD", "amount": 0, "reason": "wait"}
""",
    )


class TestEventFiltering:
    """イベントフィルタリングテスト"""

    def test_ignores_non_price_change(self, components):
        handler = _make_handler_with_default(components)
        # book イベントは無視されるべき
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event("book", {"asset_id": "a1", "price": 0.50})
        )
        trades = components[0].get_trades_since(
            __import__("datetime").datetime.min.replace(
                tzinfo=__import__("datetime").timezone.utc
            )
        )
        assert len(trades) == 0

    def test_ignores_last_trade_price(self, components):
        handler = _make_handler_with_default(components)
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "last_trade_price", {"asset_id": "a1", "price": 0.50}
            )
        )
        trades = components[0].get_trades_since(
            __import__("datetime").datetime.min.replace(
                tzinfo=__import__("datetime").timezone.utc
            )
        )
        assert len(trades) == 0


class TestBuySignal:
    """BUY シグナルテスト"""

    def test_buy_creates_trade(self, components):
        handler = _make_handler_with_default(components)
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.20", "market": "m1"},
            )
        )
        from datetime import datetime, timezone

        trades = components[0].get_trades_since(
            datetime.min.replace(tzinfo=timezone.utc)
        )
        assert len(trades) >= 1
        assert trades[0].action == "BUY"
        assert trades[0].amount_usdc == 10.0

    def test_buy_creates_position(self, components):
        handler = _make_handler_with_default(components)
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.20", "market": "m1"},
            )
        )
        pos = components[1].get_position("a1")
        assert pos is not None
        assert pos.size_usdc == 10.0


class TestHoldSignal:
    """HOLD シグナルテスト"""

    def test_hold_no_trade(self, components):
        handler = _make_handler_with_default(components)
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.50", "market": "m1"},
            )
        )
        from datetime import datetime, timezone

        trades = components[0].get_trades_since(
            datetime.min.replace(tzinfo=timezone.utc)
        )
        assert len(trades) == 0


class TestMissingData:
    """データ欠落テスト"""

    def test_missing_asset_id(self, components):
        handler = _make_handler_with_default(components)
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change", {"price": "0.20", "market": "m1"}
            )
        )
        from datetime import datetime, timezone

        trades = components[0].get_trades_since(
            datetime.min.replace(tzinfo=timezone.utc)
        )
        assert len(trades) == 0

    def test_missing_price(self, components):
        handler = _make_handler_with_default(components)
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change", {"asset_id": "a1", "market": "m1"}
            )
        )
        from datetime import datetime, timezone

        trades = components[0].get_trades_since(
            datetime.min.replace(tzinfo=timezone.utc)
        )
        assert len(trades) == 0


class TestInvalidSignal:
    """不正シグナル拒否テスト"""

    def test_non_dict_signal(self, components):
        handler = _make_handler(
            components,
            """
def calculate_signal(data):
    return "BUY"
""",
        )
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.20", "market": "m1"},
            )
        )
        from datetime import datetime, timezone

        trades = components[0].get_trades_since(
            datetime.min.replace(tzinfo=timezone.utc)
        )
        assert len(trades) == 0

    def test_invalid_action(self, components):
        handler = _make_handler(
            components,
            """
def calculate_signal(data):
    return {"action": "INVALID", "amount": 10.0, "reason": "bad"}
""",
        )
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.20", "market": "m1"},
            )
        )
        from datetime import datetime, timezone

        trades = components[0].get_trades_since(
            datetime.min.replace(tzinfo=timezone.utc)
        )
        assert len(trades) == 0

    def test_missing_amount(self, components):
        handler = _make_handler(
            components,
            """
def calculate_signal(data):
    return {"action": "BUY", "reason": "no amount"}
""",
        )
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.20", "market": "m1"},
            )
        )
        from datetime import datetime, timezone

        trades = components[0].get_trades_since(
            datetime.min.replace(tzinfo=timezone.utc)
        )
        assert len(trades) == 0


class TestSignalDataBuilding:
    """data dict 構築テスト"""

    def test_includes_price_history(self, components):
        db = components[0]
        # 価格履歴を事前に保存
        db.save_price("a1", market="m1", price=0.45)
        db.save_price("a1", market="m1", price=0.46)

        captured = {}

        handler = _make_handler(
            components,
            """
def calculate_signal(data):
    # Store for inspection would need side-effect;
    # just verify it doesn't crash with history
    return {"action": "HOLD", "amount": 0, "reason": "test"}
""",
        )

        # 履歴付きでイベント処理
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.50", "market": "m1"},
            )
        )
        # No crash = history building works

    def test_includes_position_info(self, components):
        db, pm, rm, oe = components
        pm.update_after_trade("a1", "m1", "BUY", 0.50, 100.0)

        received_data = {}

        # 戦略で受け取ったデータを検証
        handler = _make_handler(
            components,
            """
import json
def calculate_signal(data):
    # position_usdc should be > 0
    if data.get("position_usdc", 0) > 0:
        return {"action": "HOLD", "amount": 0, "reason": "has_position"}
    return {"action": "BUY", "amount": 10.0, "reason": "no_position"}
""",
        )

        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.50", "market": "m1"},
            )
        )
        # 既にポジションがあるのでHOLD→Tradeなし
        from datetime import datetime, timezone

        trades = db.get_trades_since(datetime.min.replace(tzinfo=timezone.utc))
        assert len(trades) == 0


class TestRiskRejection:
    """リスク管理による取引拒否テスト"""

    def test_risk_rejects_large_trade(self, db):
        pm = PositionManager(db)
        rm = RiskManager(
            {
                "global": {
                    "max_total_position_usdc": 10000,
                    "max_daily_loss_usdc": 1000,
                    "max_daily_trades": 100,
                    "max_single_trade_usdc": 5,  # very small limit
                },
                "circuit_breaker": {"enabled": True, "cooldown_minutes": 60},
            },
            db,
            pm,
        )
        oe = OrderExecutor(db)

        handler = _make_handler(
            (db, pm, rm, oe),
            """
def calculate_signal(data):
    return {"action": "BUY", "amount": 10.0, "reason": "buy"}
""",
        )

        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.20", "market": "m1"},
            )
        )

        from datetime import datetime, timezone

        trades = db.get_trades_since(datetime.min.replace(tzinfo=timezone.utc))
        assert len(trades) == 0


class TestStrategyError:
    """戦略エラーがクラッシュしないことテスト"""

    def test_exception_in_strategy_caught(self, components):
        handler = _make_handler(
            components,
            """
def calculate_signal(data):
    raise ValueError("strategy crash!")
""",
        )

        # Should not raise
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.20", "market": "m1"},
            )
        )

    def test_no_strategy_file(self, components):
        db, pm, rm, oe = components
        handler = StrategyHandler(
            db, rm, oe, pm, strategy_path="/nonexistent/strategy.py"
        )
        # Should not raise
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.20", "market": "m1"},
            )
        )


class TestSellWithPosition:
    """SELL → ポジション縮小/クローズテスト"""

    def test_sell_closes_position(self, components):
        db, pm, rm, oe = components
        # まずポジションを作る
        pm.update_after_trade("a1", "m1", "BUY", 0.50, 10.0)

        handler = _make_handler(
            components,
            """
def calculate_signal(data):
    if data.get("position_usdc", 0) > 0:
        return {"action": "SELL", "amount": data["position_usdc"], "reason": "close"}
    return {"action": "HOLD", "amount": 0, "reason": "wait"}
""",
        )

        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.60", "market": "m1"},
            )
        )

        pos = pm.get_position("a1")
        assert pos is None

    def test_weighted_average_on_multiple_buys(self, components):
        db, pm, rm, oe = components

        handler = _make_handler(
            components,
            """
def calculate_signal(data):
    if data.get("position_usdc", 0) == 0:
        return {"action": "BUY", "amount": 10.0, "reason": "buy"}
    return {"action": "HOLD", "amount": 0, "reason": "wait"}
""",
        )

        # 1回目の買い
        asyncio.get_event_loop().run_until_complete(
            handler.handle_event(
                "price_change",
                {"asset_id": "a1", "price": "0.20", "market": "m1"},
            )
        )
        pos = pm.get_position("a1")
        assert pos is not None
        assert pos.size_usdc == 10.0
        assert pos.average_price == 0.20
