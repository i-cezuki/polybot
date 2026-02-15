"""バックテストエンジン

calculate_signal(data) を各ティックで呼び出し、シミュレーション実行する。
PositionManager の P&L 式と OrderExecutor のスリッページ計算をインメモリで再現。
"""
from collections import deque
from typing import Any, Callable, Optional

from loguru import logger


class _Position:
    """インメモリ軽量ポジション"""
    __slots__ = ("asset_id", "market", "side", "size_usdc", "average_price")

    def __init__(
        self,
        asset_id: str,
        market: str,
        side: str = "BUY",
        size_usdc: float = 0.0,
        average_price: float = 0.0,
    ):
        self.asset_id = asset_id
        self.market = market
        self.side = side
        self.size_usdc = size_usdc
        self.average_price = average_price


class BacktestEngine:
    """バックテストコアエンジン

    Args:
        calculate_signal: シグナル計算関数 (data) -> {action, amount, reason}
        initial_capital: 初期資金 (USDC)
        slippage_config: スリッページ設定 dict
            - use_book_price: bool (default True)
            - slippage_bps: float (default 0)
    """

    def __init__(
        self,
        calculate_signal: Callable[[dict], dict],
        initial_capital: float = 10000.0,
        slippage_config: Optional[dict] = None,
    ):
        self._calculate_signal = calculate_signal
        self._initial_capital = initial_capital

        config = slippage_config or {}
        self._use_book_price = config.get("use_book_price", True)
        self._slippage_bps = config.get("slippage_bps", 0)

    def run(self, ticks: list[dict]) -> dict:
        """バックテスト実行

        Args:
            ticks: timestamp 昇順のティックデータ

        Returns:
            {trades, equity_curve, final_capital, positions, initial_capital}
        """
        capital = self._initial_capital
        positions: dict[str, _Position] = {}
        trades: list[dict] = []
        equity_curve: list[dict] = []
        history_buffers: dict[str, deque] = {}
        last_prices: dict[str, float] = {}

        for tick in ticks:
            asset_id = tick.get("asset_id", "")
            price = tick.get("price")
            if price is None or asset_id == "":
                continue

            price = float(price)
            last_prices[asset_id] = price

            # history_buffer 更新
            if asset_id not in history_buffers:
                history_buffers[asset_id] = deque(maxlen=100)
            history_buffers[asset_id].append({
                "price": price,
                "timestamp": tick.get("timestamp", ""),
            })

            # signal_data 構築
            signal_data = self._build_signal_data(
                tick, asset_id, price, positions, history_buffers
            )

            # シグナル計算
            try:
                signal = self._calculate_signal(signal_data)
            except Exception as e:
                logger.warning(f"シグナル計算エラー: {e}")
                continue

            if not isinstance(signal, dict):
                continue

            action = signal.get("action", "HOLD")
            amount = signal.get("amount", 0)
            reason = signal.get("reason", "")

            if action == "BUY" and amount > 0:
                exec_price = self._calc_execution_price(
                    "BUY", price, tick.get("best_bid"), tick.get("best_ask")
                )
                result = self._process_buy(
                    asset_id, tick.get("market", ""), exec_price,
                    amount, capital, positions,
                )
                if result is not None:
                    capital = result["capital"]
                    trades.append({
                        "action": "BUY",
                        "asset_id": asset_id,
                        "price": exec_price,
                        "amount_usdc": result["amount_usdc"],
                        "realized_pnl": 0.0,
                        "reason": reason,
                        "timestamp": tick.get("timestamp", ""),
                    })

            elif action == "SELL" and amount > 0:
                exec_price = self._calc_execution_price(
                    "SELL", price, tick.get("best_bid"), tick.get("best_ask")
                )
                result = self._process_sell(
                    asset_id, exec_price, amount, capital, positions,
                )
                if result is not None:
                    capital = result["capital"]
                    trades.append({
                        "action": "SELL",
                        "asset_id": asset_id,
                        "price": exec_price,
                        "amount_usdc": result["sell_usdc"],
                        "realized_pnl": result["realized_pnl"],
                        "reason": reason,
                        "timestamp": tick.get("timestamp", ""),
                    })

            # エクイティ記録
            equity = self._calc_equity(capital, positions, last_prices)
            equity_curve.append({
                "timestamp": tick.get("timestamp", ""),
                "equity": equity,
                "capital": capital,
            })

        # 未決済ポジションを最終価格で強制クローズ
        for asset_id in list(positions.keys()):
            pos = positions[asset_id]
            if pos.size_usdc <= 0:
                continue
            close_price = last_prices.get(asset_id, pos.average_price)
            result = self._process_sell(
                asset_id, close_price, pos.size_usdc, capital, positions,
            )
            if result is not None:
                capital = result["capital"]
                trades.append({
                    "action": "SELL",
                    "asset_id": asset_id,
                    "price": close_price,
                    "amount_usdc": result["sell_usdc"],
                    "realized_pnl": result["realized_pnl"],
                    "reason": "バックテスト終了: 強制クローズ",
                    "timestamp": "",
                })

        return {
            "trades": trades,
            "equity_curve": equity_curve,
            "final_capital": capital,
            "initial_capital": self._initial_capital,
            "positions": {
                aid: {
                    "size_usdc": p.size_usdc,
                    "average_price": p.average_price,
                }
                for aid, p in positions.items()
                if p.size_usdc > 0
            },
        }

    def _build_signal_data(
        self,
        tick: dict,
        asset_id: str,
        price: float,
        positions: dict[str, _Position],
        history_buffers: dict[str, deque],
    ) -> dict:
        """calculate_signal に渡す data dict を構築

        StrategyHandler._build_signal_data() と同一スキーマ。
        """
        pos = positions.get(asset_id)
        position_usdc = pos.size_usdc if pos else 0.0
        side = pos.side if pos else None

        history = list(history_buffers.get(asset_id, []))

        return {
            "price": price,
            "market_id": tick.get("market", ""),
            "history": history,
            "position_usdc": position_usdc,
            "side": side,
            "best_bid": tick.get("best_bid"),
            "best_ask": tick.get("best_ask"),
            "timestamp": tick.get("timestamp"),
        }

    def _calc_execution_price(
        self,
        action: str,
        price: float,
        best_bid: Any = None,
        best_ask: Any = None,
    ) -> float:
        """約定価格を算出（OrderExecutor.calc_execution_price と同一ロジック）"""
        base = price

        if self._use_book_price:
            if action == "BUY" and best_ask is not None:
                base = float(best_ask)
            elif action == "SELL" and best_bid is not None:
                base = float(best_bid)

        slip = self._slippage_bps / 10000
        if action == "BUY":
            exec_price = base * (1 + slip)
        else:
            exec_price = base * (1 - slip)

        return round(exec_price, 6)

    @staticmethod
    def _process_buy(
        asset_id: str,
        market: str,
        exec_price: float,
        amount_usdc: float,
        capital: float,
        positions: dict[str, _Position],
    ) -> Optional[dict]:
        """BUY 処理（PositionManager.update_after_trade BUY と同一ロジック）"""
        if amount_usdc > capital:
            logger.debug(f"資金不足: 必要={amount_usdc:.2f}, 残={capital:.2f}")
            return None

        pos = positions.get(asset_id)
        if pos is None:
            positions[asset_id] = _Position(
                asset_id=asset_id,
                market=market,
                side="BUY",
                size_usdc=amount_usdc,
                average_price=exec_price,
            )
        else:
            total_usdc = round(pos.size_usdc + amount_usdc, 6)
            new_avg = round(
                (pos.average_price * pos.size_usdc + exec_price * amount_usdc)
                / total_usdc,
                6,
            )
            pos.size_usdc = total_usdc
            pos.average_price = new_avg

        return {
            "capital": capital - amount_usdc,
            "amount_usdc": amount_usdc,
        }

    @staticmethod
    def _process_sell(
        asset_id: str,
        exec_price: float,
        amount_usdc: float,
        capital: float,
        positions: dict[str, _Position],
    ) -> Optional[dict]:
        """SELL 処理（PositionManager.update_after_trade SELL と同一ロジック）"""
        pos = positions.get(asset_id)
        if pos is None or pos.size_usdc <= 0:
            return None

        sell_usdc = round(min(amount_usdc, pos.size_usdc), 6)

        realized_pnl = 0.0
        if pos.average_price > 0:
            realized_pnl = round(
                sell_usdc * (exec_price - pos.average_price) / pos.average_price,
                6,
            )

        remaining = round(pos.size_usdc - sell_usdc, 6)

        if remaining <= 0.001:
            pos.size_usdc = 0.0
            pos.average_price = 0.0
        else:
            pos.size_usdc = remaining

        return {
            "capital": capital + sell_usdc + realized_pnl,
            "sell_usdc": sell_usdc,
            "realized_pnl": realized_pnl,
        }

    @staticmethod
    def _calc_equity(
        capital: float,
        positions: dict[str, _Position],
        last_prices: dict[str, float],
    ) -> float:
        """現在のエクイティ（資金 + 未実現含み益/損）を計算"""
        equity = capital
        for asset_id, pos in positions.items():
            if pos.size_usdc <= 0 or pos.average_price <= 0:
                continue
            current_price = last_prices.get(asset_id, pos.average_price)
            equity += pos.size_usdc * current_price / pos.average_price
        return round(equity, 6)
