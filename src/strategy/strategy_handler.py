"""戦略ハンドラーモジュール"""
import importlib.util
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from loguru import logger

from database.db_manager import DatabaseManager
from executor.order_executor import OrderExecutor
from executor.position_manager import PositionManager
from risk.risk_manager import RiskManager


def _to_float(value) -> Optional[float]:
    """値を float に安全変換（None/不正値は None を返す）"""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class StrategyHandler:
    """戦略ハンドラー

    PriceMonitor の add_handler に登録し、price_change イベントを受けて
    ユーザー戦略 (calculate_signal) を実行する。
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        risk_manager: RiskManager,
        order_executor: OrderExecutor,
        position_manager: PositionManager,
        strategy_path: str = "config/strategy.py",
    ):
        self.db_manager = db_manager
        self.risk_manager = risk_manager
        self.order_executor = order_executor
        self.position_manager = position_manager
        self._calculate_signal: Optional[Callable] = None

        self._load_strategy(strategy_path)
        logger.info(f"StrategyHandler initialized: strategy={strategy_path}")

    def _load_strategy(self, strategy_path: str) -> None:
        """config/strategy.py から calculate_signal を動的ロード"""
        path = Path(strategy_path)
        if not path.exists():
            logger.warning(f"戦略ファイルが見つかりません: {strategy_path}")
            return

        try:
            spec = importlib.util.spec_from_file_location("user_strategy", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "calculate_signal"):
                self._calculate_signal = module.calculate_signal
                logger.info(f"戦略ロード完了: {strategy_path}")
            else:
                logger.warning(
                    f"calculate_signal() が見つかりません: {strategy_path}"
                )
        except Exception as e:
            logger.error(f"戦略ロードエラー: {e}")

    async def handle_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """PriceMonitor からのイベントを処理"""
        if event_type != "price_change":
            return

        if self._calculate_signal is None:
            return

        asset_id = data.get("asset_id")
        price = data.get("price")

        if not asset_id or price is None:
            return

        try:
            price = float(price)
        except (TypeError, ValueError):
            return

        try:
            signal_data = self._build_signal_data(data, asset_id, price)
            signal = self._calculate_signal(signal_data)

            if not self._validate_signal(signal):
                return

            action = signal["action"]
            if action == "HOLD":
                return

            amount = float(signal["amount"])
            reason = signal.get("reason", "")

            if amount <= 0:
                return

            # リスクチェック
            if not self.risk_manager.check_order(asset_id, action, amount):
                logger.info(
                    f"[STRATEGY] リスク拒否: {action} {amount:.2f} USDC | "
                    f"{asset_id[:16]}..."
                )
                return

            # 注文実行（シミュレーション・スリッページ込み）
            best_bid = _to_float(data.get("best_bid"))
            best_ask = _to_float(data.get("best_ask"))

            result = self.order_executor.execute(
                asset_id=asset_id,
                market=data.get("market"),
                action=action,
                price=price,
                amount_usdc=amount,
                reason=reason,
                best_bid=best_bid,
                best_ask=best_ask,
            )

            if result is not None:
                trade_id, exec_price = result

                # ポジション更新（スリッページ適用後の約定価格を使用）
                realized_pnl = self.position_manager.update_after_trade(
                    asset_id=asset_id,
                    market=data.get("market"),
                    action=action,
                    price=exec_price,
                    amount_usdc=amount,
                )

                # 実現P&Lがあれば Trade レコードを更新
                if realized_pnl != 0.0:
                    self.db_manager.save_trade(
                        asset_id=asset_id,
                        market=data.get("market"),
                        action=action,
                        price=exec_price,
                        amount_usdc=amount,
                        realized_pnl=realized_pnl,
                        reason=f"P&L update: {reason}",
                    )

        except Exception as e:
            logger.error(f"[STRATEGY] 戦略実行エラー: {e}", exc_info=True)

    def _build_signal_data(
        self, data: Dict[str, Any], asset_id: str, price: float
    ) -> Dict[str, Any]:
        """calculate_signal に渡す data dict を構築"""
        # 価格履歴
        market = data.get("market", "")
        history = []
        if market:
            price_records = self.db_manager.get_price_history(market, minutes=30)
            history = [
                {"price": float(r.price), "timestamp": str(r.timestamp)}
                for r in price_records
                if r.price is not None
            ]

        # ポジション情報
        position = self.position_manager.get_position(asset_id)
        position_usdc = position.size_usdc if position else 0.0
        side = position.side if position else None

        return {
            "price": price,
            "market_id": market,
            "history": history,
            "position_usdc": position_usdc,
            "side": side,
            "best_bid": data.get("best_bid"),
            "best_ask": data.get("best_ask"),
            "timestamp": data.get("timestamp"),
        }

    def _validate_signal(self, signal: Any) -> bool:
        """戦略の戻り値を検証"""
        if not isinstance(signal, dict):
            logger.warning(f"[STRATEGY] 不正シグナル（dict以外）: {type(signal)}")
            return False

        action = signal.get("action")
        if action not in ("BUY", "SELL", "HOLD"):
            logger.warning(f"[STRATEGY] 不正action: {action}")
            return False

        if action != "HOLD":
            amount = signal.get("amount")
            if amount is None:
                logger.warning("[STRATEGY] amount が未設定")
                return False
            try:
                float(amount)
            except (TypeError, ValueError):
                logger.warning(f"[STRATEGY] 不正amount: {amount}")
                return False

        return True
