"""パフォーマンス分析モジュール

バックテスト結果からメトリクスを計算し、レポートを生成する。
"""
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Docker 内でのヘッドレス描画
import matplotlib.pyplot as plt
import numpy as np
from loguru import logger


class PerformanceAnalyzer:
    """バックテスト結果のパフォーマンス分析"""

    def analyze(self, backtest_results: dict) -> dict:
        """バックテスト結果を分析

        Args:
            backtest_results: BacktestEngine.run() の戻り値

        Returns:
            分析結果 dict
        """
        trades = backtest_results.get("trades", [])
        equity_curve = backtest_results.get("equity_curve", [])
        initial_capital = backtest_results.get("initial_capital", 10000.0)
        final_capital = backtest_results.get("final_capital", initial_capital)

        total_pnl = final_capital - initial_capital
        total_return_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else 0.0

        # 取引分析
        sell_trades = [t for t in trades if t.get("action") == "SELL"]
        total_trades = len(sell_trades)

        winning_trades = [t for t in sell_trades if t.get("realized_pnl", 0) > 0]
        losing_trades = [t for t in sell_trades if t.get("realized_pnl", 0) < 0]

        win_count = len(winning_trades)
        lose_count = len(losing_trades)
        win_rate_pct = (win_count / total_trades * 100) if total_trades > 0 else 0.0

        avg_win = (
            sum(t["realized_pnl"] for t in winning_trades) / win_count
            if win_count > 0
            else 0.0
        )
        avg_loss = (
            sum(t["realized_pnl"] for t in losing_trades) / lose_count
            if lose_count > 0
            else 0.0
        )
        payoff_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0

        # シャープレシオ
        sharpe_ratio = self._calc_sharpe_ratio(equity_curve)

        # 最大ドローダウン
        max_drawdown_pct = self._calc_max_drawdown(equity_curve)

        return {
            "total_pnl": round(total_pnl, 6),
            "total_return_pct": round(total_return_pct, 4),
            "total_trades": total_trades,
            "winning_trades": win_count,
            "losing_trades": lose_count,
            "win_rate_pct": round(win_rate_pct, 2),
            "avg_win": round(avg_win, 6),
            "avg_loss": round(avg_loss, 6),
            "payoff_ratio": round(payoff_ratio, 4),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "max_drawdown_pct": round(max_drawdown_pct, 4),
            "initial_capital": initial_capital,
            "final_capital": round(final_capital, 6),
        }

    @staticmethod
    def _calc_sharpe_ratio(equity_curve: list[dict]) -> float:
        """シャープレシオを計算（年率換算）"""
        if len(equity_curve) < 2:
            return 0.0

        equities = [e["equity"] for e in equity_curve]
        returns = []
        for i in range(1, len(equities)):
            if equities[i - 1] > 0:
                returns.append((equities[i] - equities[i - 1]) / equities[i - 1])

        if not returns:
            return 0.0

        arr = np.array(returns)
        std = float(np.std(arr))
        if std == 0:
            return 0.0

        mean_return = float(np.mean(arr))
        # 年率換算（ティック単位 → 概算で日次 252 営業日）
        annualize = math.sqrt(min(len(returns), 252))
        return mean_return / std * annualize

    @staticmethod
    def _calc_max_drawdown(equity_curve: list[dict]) -> float:
        """最大ドローダウンをパーセントで計算"""
        if not equity_curve:
            return 0.0

        equities = np.array([e["equity"] for e in equity_curve])
        if len(equities) == 0:
            return 0.0

        running_max = np.maximum.accumulate(equities)
        # ゼロ除算防止
        safe_max = np.where(running_max > 0, running_max, 1.0)
        drawdowns = (running_max - equities) / safe_max * 100

        return float(np.max(drawdowns))

    def generate_report(
        self,
        analysis: dict,
        output_dir: str = "reports",
    ) -> Path:
        """レポートファイルを生成

        Args:
            analysis: analyze() の戻り値
            output_dir: 出力ディレクトリ

        Returns:
            出力ディレクトリの Path
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        self._write_summary(analysis, out / "summary.txt")
        logger.info(f"サマリーレポート生成: {out / 'summary.txt'}")

        return out

    def generate_report_with_charts(
        self,
        analysis: dict,
        backtest_results: dict,
        output_dir: str = "reports",
    ) -> Path:
        """チャート付きレポートを生成

        Args:
            analysis: analyze() の戻り値
            backtest_results: BacktestEngine.run() の戻り値
            output_dir: 出力ディレクトリ

        Returns:
            出力ディレクトリの Path
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        self._write_summary(analysis, out / "summary.txt")

        equity_curve = backtest_results.get("equity_curve", [])
        trades = backtest_results.get("trades", [])

        if equity_curve:
            self._plot_equity_curve(equity_curve, out / "equity_curve.png")
            logger.info(f"エクイティカーブ生成: {out / 'equity_curve.png'}")

        sell_trades = [t for t in trades if t.get("action") == "SELL"]
        if sell_trades:
            self._plot_trade_pnl(sell_trades, out / "trade_pnl.png")
            logger.info(f"取引P&L散布図生成: {out / 'trade_pnl.png'}")

        return out

    @staticmethod
    def _write_summary(analysis: dict, filepath: Path) -> None:
        """テキストサマリーを書き出し"""
        lines = [
            "=" * 50,
            "  バックテスト パフォーマンスサマリー",
            "=" * 50,
            "",
            f"初期資金:        {analysis.get('initial_capital', 0):>12.2f} USDC",
            f"最終資金:        {analysis.get('final_capital', 0):>12.2f} USDC",
            f"損益合計:        {analysis.get('total_pnl', 0):>12.2f} USDC",
            f"リターン:        {analysis.get('total_return_pct', 0):>11.2f}%",
            "",
            f"総取引数:        {analysis.get('total_trades', 0):>12d}",
            f"勝ち取引:        {analysis.get('winning_trades', 0):>12d}",
            f"負け取引:        {analysis.get('losing_trades', 0):>12d}",
            f"勝率:            {analysis.get('win_rate_pct', 0):>11.2f}%",
            "",
            f"平均勝ち:        {analysis.get('avg_win', 0):>12.4f} USDC",
            f"平均負け:        {analysis.get('avg_loss', 0):>12.4f} USDC",
            f"ペイオフレシオ:  {analysis.get('payoff_ratio', 0):>12.4f}",
            "",
            f"シャープレシオ:  {analysis.get('sharpe_ratio', 0):>12.4f}",
            f"最大DD:          {analysis.get('max_drawdown_pct', 0):>11.4f}%",
            "",
            "=" * 50,
        ]
        filepath.write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _plot_equity_curve(equity_curve: list[dict], filepath: Path) -> None:
        """エクイティカーブを描画"""
        equities = [e["equity"] for e in equity_curve]

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(equities, linewidth=1.0, color="blue")
        ax.set_title("Equity Curve")
        ax.set_xlabel("Tick")
        ax.set_ylabel("Equity (USDC)")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(filepath, dpi=100)
        plt.close(fig)

    @staticmethod
    def _plot_trade_pnl(sell_trades: list[dict], filepath: Path) -> None:
        """取引 P&L 散布図を描画（勝ち=緑, 負け=赤）"""
        pnls = [t.get("realized_pnl", 0) for t in sell_trades]
        colors = ["green" if p > 0 else "red" for p in pnls]
        indices = list(range(len(pnls)))

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.scatter(indices, pnls, c=colors, alpha=0.6, s=20)
        ax.axhline(y=0, color="black", linewidth=0.5)
        ax.set_title("Trade P&L")
        ax.set_xlabel("Trade #")
        ax.set_ylabel("Realized P&L (USDC)")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(filepath, dpi=100)
        plt.close(fig)
