"""PerformanceAnalyzer テスト"""
import tempfile
from pathlib import Path

import pytest

from backtester.performance_analyzer import PerformanceAnalyzer


def _make_backtest_result(
    trades=None,
    equity_curve=None,
    initial_capital=10000.0,
    final_capital=10000.0,
):
    return {
        "trades": trades or [],
        "equity_curve": equity_curve or [],
        "initial_capital": initial_capital,
        "final_capital": final_capital,
        "positions": {},
    }


def _make_sell_trade(pnl, amount=10.0):
    return {
        "action": "SELL",
        "asset_id": "asset1",
        "price": 0.5,
        "amount_usdc": amount,
        "realized_pnl": pnl,
        "reason": "test",
        "timestamp": "2026-02-14T10:00:00Z",
    }


class TestWinRate:
    """勝率計算"""

    def test_all_wins(self):
        trades = [_make_sell_trade(5.0), _make_sell_trade(3.0)]
        result = _make_backtest_result(trades=trades, final_capital=10008.0)
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["win_rate_pct"] == 100.0
        assert analysis["total_trades"] == 2
        assert analysis["winning_trades"] == 2
        assert analysis["losing_trades"] == 0

    def test_all_losses(self):
        trades = [_make_sell_trade(-5.0), _make_sell_trade(-3.0)]
        result = _make_backtest_result(trades=trades, final_capital=9992.0)
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["win_rate_pct"] == 0.0
        assert analysis["losing_trades"] == 2

    def test_mixed(self):
        trades = [_make_sell_trade(10.0), _make_sell_trade(-5.0), _make_sell_trade(3.0)]
        result = _make_backtest_result(trades=trades, final_capital=10008.0)
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["win_rate_pct"] == pytest.approx(66.67, abs=0.01)
        assert analysis["winning_trades"] == 2
        assert analysis["losing_trades"] == 1


class TestAvgWinLoss:
    """平均勝ち・負け・ペイオフレシオ"""

    def test_avg_win_loss(self):
        trades = [_make_sell_trade(10.0), _make_sell_trade(6.0), _make_sell_trade(-4.0)]
        result = _make_backtest_result(trades=trades, final_capital=10012.0)
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["avg_win"] == pytest.approx(8.0, abs=0.01)
        assert analysis["avg_loss"] == pytest.approx(-4.0, abs=0.01)
        assert analysis["payoff_ratio"] == pytest.approx(2.0, abs=0.01)


class TestSharpeRatio:
    """シャープレシオ（既知入力）"""

    def test_constant_equity_zero_sharpe(self):
        """一定のエクイティ → シャープ = 0（std = 0）"""
        equity = [{"equity": 10000.0, "timestamp": ""} for _ in range(10)]
        result = _make_backtest_result(equity_curve=equity)
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["sharpe_ratio"] == 0.0

    def test_positive_sharpe(self):
        """上昇トレンドのエクイティ → 正のシャープ"""
        equity = [{"equity": 10000.0 + i * 100, "timestamp": ""} for i in range(20)]
        result = _make_backtest_result(
            equity_curve=equity, final_capital=11900.0,
        )
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["sharpe_ratio"] > 0

    def test_single_point_zero_sharpe(self):
        """1点 → シャープ = 0"""
        equity = [{"equity": 10000.0, "timestamp": ""}]
        result = _make_backtest_result(equity_curve=equity)
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["sharpe_ratio"] == 0.0


class TestMaxDrawdown:
    """最大ドローダウン（既知入力）"""

    def test_no_drawdown(self):
        """単調増加 → DD = 0"""
        equity = [{"equity": 10000.0 + i * 100, "timestamp": ""} for i in range(5)]
        result = _make_backtest_result(equity_curve=equity)
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["max_drawdown_pct"] == pytest.approx(0.0, abs=0.01)

    def test_known_drawdown(self):
        """10000 → 12000 → 9000 → 10000: DD = (12000-9000)/12000 = 25%"""
        equity = [
            {"equity": 10000, "timestamp": ""},
            {"equity": 12000, "timestamp": ""},
            {"equity": 9000, "timestamp": ""},
            {"equity": 10000, "timestamp": ""},
        ]
        result = _make_backtest_result(equity_curve=equity)
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["max_drawdown_pct"] == pytest.approx(25.0, abs=0.01)

    def test_empty_equity_curve(self):
        result = _make_backtest_result(equity_curve=[])
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["max_drawdown_pct"] == 0.0


class TestZeroTrades:
    """取引ゼロでエラーなし"""

    def test_no_trades(self):
        result = _make_backtest_result()
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["total_trades"] == 0
        assert analysis["win_rate_pct"] == 0.0
        assert analysis["avg_win"] == 0.0
        assert analysis["avg_loss"] == 0.0
        assert analysis["payoff_ratio"] == 0.0
        assert analysis["total_pnl"] == 0.0


class TestReportGeneration:
    """レポートファイル生成確認"""

    def test_summary_txt_generated(self, tmp_path):
        result = _make_backtest_result(final_capital=10500.0)
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        out = analyzer.generate_report(analysis, output_dir=str(tmp_path))

        summary_path = tmp_path / "summary.txt"
        assert summary_path.exists()
        content = summary_path.read_text(encoding="utf-8")
        assert "パフォーマンスサマリー" in content
        assert "10500" in content

    def test_charts_generated(self, tmp_path):
        trades = [_make_sell_trade(5.0), _make_sell_trade(-2.0)]
        equity = [
            {"equity": 10000, "timestamp": ""},
            {"equity": 10005, "timestamp": ""},
            {"equity": 10003, "timestamp": ""},
        ]
        result = _make_backtest_result(
            trades=trades, equity_curve=equity, final_capital=10003.0,
        )
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        out = analyzer.generate_report_with_charts(
            analysis, result, output_dir=str(tmp_path)
        )

        assert (tmp_path / "summary.txt").exists()
        assert (tmp_path / "equity_curve.png").exists()
        assert (tmp_path / "trade_pnl.png").exists()


class TestTotalReturn:
    """トータルリターン計算"""

    def test_positive_return(self):
        result = _make_backtest_result(
            initial_capital=10000.0, final_capital=11000.0,
        )
        analyzer = PerformanceAnalyzer()
        analysis = analyzer.analyze(result)

        assert analysis["total_return_pct"] == pytest.approx(10.0, abs=0.01)
        assert analysis["total_pnl"] == pytest.approx(1000.0, abs=0.01)
