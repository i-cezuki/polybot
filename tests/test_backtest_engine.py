"""BacktestEngine テスト"""
import pytest

from backtester.backtest_engine import BacktestEngine


def _make_tick(
    asset_id="asset1",
    market="0xabc",
    price=0.50,
    best_bid=None,
    best_ask=None,
    timestamp="2026-02-14T10:00:00Z",
):
    return {
        "asset_id": asset_id,
        "market": market,
        "price": price,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "timestamp": timestamp,
    }


class TestHoldStrategy:
    """HOLD 戦略で取引ゼロ"""

    def test_no_trades(self):
        def hold_strategy(data):
            return {"action": "HOLD", "amount": 0, "reason": "always hold"}

        engine = BacktestEngine(hold_strategy, initial_capital=10000.0)
        ticks = [_make_tick(timestamp=f"2026-02-14T10:0{i}:00Z") for i in range(5)]
        result = engine.run(ticks)

        assert len(result["trades"]) == 0
        assert result["final_capital"] == 10000.0
        assert result["initial_capital"] == 10000.0


class TestBuySell:
    """BUY → SELL で正しい P&L"""

    def test_simple_buy_sell(self):
        """price=0.20 で BUY 10 USDC → price=0.40 で SELL → pnl = 10.0"""
        call_count = [0]

        def strategy(data):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"action": "BUY", "amount": 10.0, "reason": "buy"}
            elif call_count[0] == 2:
                return {"action": "SELL", "amount": 10.0, "reason": "sell"}
            return {"action": "HOLD", "amount": 0, "reason": "done"}

        engine = BacktestEngine(
            strategy,
            initial_capital=10000.0,
            slippage_config={"use_book_price": False, "slippage_bps": 0},
        )
        ticks = [
            _make_tick(price=0.20, timestamp="2026-02-14T10:00:00Z"),
            _make_tick(price=0.40, timestamp="2026-02-14T10:01:00Z"),
        ]
        result = engine.run(ticks)

        # BUY + SELL + forced close (none since position closed)
        sell_trades = [t for t in result["trades"] if t["action"] == "SELL"]
        assert len(sell_trades) >= 1

        pnl = sell_trades[0]["realized_pnl"]
        # pnl = 10 * (0.40 - 0.20) / 0.20 = 10.0
        assert pnl == pytest.approx(10.0, abs=0.01)

    def test_final_capital_after_buy_sell(self):
        """BUY 10 @ 0.20 → SELL @ 0.40 → capital = 10000 - 10 + 10 + 10 = 10010"""
        call_count = [0]

        def strategy(data):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"action": "BUY", "amount": 10.0, "reason": "buy"}
            elif call_count[0] == 2:
                return {"action": "SELL", "amount": 10.0, "reason": "sell"}
            return {"action": "HOLD", "amount": 0, "reason": "done"}

        engine = BacktestEngine(
            strategy,
            initial_capital=10000.0,
            slippage_config={"use_book_price": False, "slippage_bps": 0},
        )
        ticks = [
            _make_tick(price=0.20, timestamp="2026-02-14T10:00:00Z"),
            _make_tick(price=0.40, timestamp="2026-02-14T10:01:00Z"),
        ]
        result = engine.run(ticks)

        assert result["final_capital"] == pytest.approx(10010.0, abs=0.01)


class TestSlippage:
    """スリッページが OrderExecutor と一致"""

    def test_buy_slippage_with_book_price(self):
        """BUY: best_ask * (1 + slippage_bps / 10000)"""
        call_count = [0]

        def strategy(data):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"action": "BUY", "amount": 10.0, "reason": "buy"}
            return {"action": "HOLD", "amount": 0, "reason": "hold"}

        engine = BacktestEngine(
            strategy,
            initial_capital=10000.0,
            slippage_config={"use_book_price": True, "slippage_bps": 100},  # 1%
        )
        ticks = [
            _make_tick(price=0.50, best_ask=0.51, timestamp="2026-02-14T10:00:00Z"),
        ]
        result = engine.run(ticks)

        buy_trades = [t for t in result["trades"] if t["action"] == "BUY"]
        assert len(buy_trades) == 1
        # 0.51 * 1.01 = 0.5151
        assert buy_trades[0]["price"] == pytest.approx(0.5151, abs=0.0001)

    def test_sell_slippage_with_book_price(self):
        """SELL: best_bid * (1 - slippage_bps / 10000)"""
        call_count = [0]

        def strategy(data):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"action": "BUY", "amount": 10.0, "reason": "buy"}
            elif call_count[0] == 2:
                return {"action": "SELL", "amount": 10.0, "reason": "sell"}
            return {"action": "HOLD", "amount": 0, "reason": "hold"}

        engine = BacktestEngine(
            strategy,
            initial_capital=10000.0,
            slippage_config={"use_book_price": True, "slippage_bps": 100},  # 1%
        )
        ticks = [
            _make_tick(price=0.50, best_ask=0.51, timestamp="2026-02-14T10:00:00Z"),
            _make_tick(price=0.60, best_bid=0.59, timestamp="2026-02-14T10:01:00Z"),
        ]
        result = engine.run(ticks)

        sell_trades = [t for t in result["trades"] if t["action"] == "SELL"]
        assert len(sell_trades) >= 1
        # 0.59 * 0.99 = 0.5841
        assert sell_trades[0]["price"] == pytest.approx(0.5841, abs=0.0001)


class TestWeightedAverage:
    """加重平均（複数 BUY）"""

    def test_weighted_average_price(self):
        call_count = [0]

        def strategy(data):
            call_count[0] += 1
            if call_count[0] <= 2:
                return {"action": "BUY", "amount": 10.0, "reason": "buy"}
            elif call_count[0] == 3:
                return {"action": "SELL", "amount": 20.0, "reason": "sell"}
            return {"action": "HOLD", "amount": 0, "reason": "hold"}

        engine = BacktestEngine(
            strategy,
            initial_capital=10000.0,
            slippage_config={"use_book_price": False, "slippage_bps": 0},
        )
        ticks = [
            _make_tick(price=0.20, timestamp="2026-02-14T10:00:00Z"),
            _make_tick(price=0.40, timestamp="2026-02-14T10:01:00Z"),
            _make_tick(price=0.60, timestamp="2026-02-14T10:02:00Z"),
        ]
        result = engine.run(ticks)

        # avg = (0.20*10 + 0.40*10) / 20 = 0.30
        # pnl = 20 * (0.60 - 0.30) / 0.30 = 20.0
        sell_trades = [t for t in result["trades"] if t["action"] == "SELL"]
        assert len(sell_trades) >= 1
        assert sell_trades[0]["realized_pnl"] == pytest.approx(20.0, abs=0.01)


class TestPartialClose:
    """部分決済"""

    def test_partial_sell(self):
        call_count = [0]

        def strategy(data):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"action": "BUY", "amount": 20.0, "reason": "buy"}
            elif call_count[0] == 2:
                return {"action": "SELL", "amount": 10.0, "reason": "partial sell"}
            return {"action": "HOLD", "amount": 0, "reason": "hold"}

        engine = BacktestEngine(
            strategy,
            initial_capital=10000.0,
            slippage_config={"use_book_price": False, "slippage_bps": 0},
        )
        ticks = [
            _make_tick(price=0.20, timestamp="2026-02-14T10:00:00Z"),
            _make_tick(price=0.40, timestamp="2026-02-14T10:01:00Z"),
            _make_tick(price=0.40, timestamp="2026-02-14T10:02:00Z"),
        ]
        result = engine.run(ticks)

        # 部分決済: 10 * (0.40 - 0.20) / 0.20 = 10.0
        sell_trades = [t for t in result["trades"] if t["action"] == "SELL"]
        assert len(sell_trades) >= 1
        assert sell_trades[0]["realized_pnl"] == pytest.approx(10.0, abs=0.01)
        assert sell_trades[0]["amount_usdc"] == pytest.approx(10.0, abs=0.01)

        # 残ポジションが強制クローズされる
        assert len(sell_trades) >= 2  # partial sell + forced close


class TestForceClose:
    """バックテスト終了時の強制クローズ"""

    def test_open_positions_closed(self):
        call_count = [0]

        def strategy(data):
            call_count[0] += 1
            if call_count[0] == 1:
                return {"action": "BUY", "amount": 10.0, "reason": "buy"}
            return {"action": "HOLD", "amount": 0, "reason": "hold"}

        engine = BacktestEngine(
            strategy,
            initial_capital=10000.0,
            slippage_config={"use_book_price": False, "slippage_bps": 0},
        )
        ticks = [
            _make_tick(price=0.50, timestamp="2026-02-14T10:00:00Z"),
            _make_tick(price=0.60, timestamp="2026-02-14T10:01:00Z"),
        ]
        result = engine.run(ticks)

        # 最終ティック後に強制クローズ
        sell_trades = [t for t in result["trades"] if t["action"] == "SELL"]
        assert len(sell_trades) == 1
        assert "強制クローズ" in sell_trades[0]["reason"]

        # ポジション残なし
        assert len(result["positions"]) == 0


class TestInsufficientFunds:
    """資金不足時の BUY スキップ"""

    def test_skip_buy_when_insufficient(self):
        def strategy(data):
            return {"action": "BUY", "amount": 50000.0, "reason": "big buy"}

        engine = BacktestEngine(
            strategy,
            initial_capital=100.0,
            slippage_config={"use_book_price": False, "slippage_bps": 0},
        )
        ticks = [_make_tick(price=0.50, timestamp="2026-02-14T10:00:00Z")]
        result = engine.run(ticks)

        buy_trades = [t for t in result["trades"] if t["action"] == "BUY"]
        assert len(buy_trades) == 0
        assert result["final_capital"] == 100.0


class TestEquityCurve:
    """エクイティカーブの長さ"""

    def test_equity_curve_length(self):
        def hold_strategy(data):
            return {"action": "HOLD", "amount": 0, "reason": "hold"}

        engine = BacktestEngine(hold_strategy, initial_capital=10000.0)
        ticks = [_make_tick(timestamp=f"2026-02-14T10:0{i}:00Z") for i in range(5)]
        result = engine.run(ticks)

        assert len(result["equity_curve"]) == 5

    def test_equity_curve_has_timestamps(self):
        def hold_strategy(data):
            return {"action": "HOLD", "amount": 0, "reason": "hold"}

        engine = BacktestEngine(hold_strategy, initial_capital=10000.0)
        ticks = [_make_tick(timestamp="2026-02-14T10:00:00Z")]
        result = engine.run(ticks)

        assert result["equity_curve"][0]["timestamp"] == "2026-02-14T10:00:00Z"
        assert result["equity_curve"][0]["equity"] == 10000.0


class TestSignalError:
    """シグナル計算エラー時にクラッシュしない"""

    def test_exception_in_signal(self):
        call_count = [0]

        def bad_strategy(data):
            call_count[0] += 1
            if call_count[0] == 1:
                raise ValueError("intentional error")
            return {"action": "HOLD", "amount": 0, "reason": "ok"}

        engine = BacktestEngine(bad_strategy, initial_capital=10000.0)
        ticks = [
            _make_tick(timestamp="2026-02-14T10:00:00Z"),
            _make_tick(timestamp="2026-02-14T10:01:00Z"),
        ]
        result = engine.run(ticks)

        assert result["final_capital"] == 10000.0

    def test_non_dict_signal(self):
        def bad_strategy(data):
            return "not a dict"

        engine = BacktestEngine(bad_strategy, initial_capital=10000.0)
        ticks = [_make_tick(timestamp="2026-02-14T10:00:00Z")]
        result = engine.run(ticks)

        assert len(result["trades"]) == 0
