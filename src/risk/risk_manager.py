"""リスク管理モジュール"""
from datetime import datetime, timedelta, timezone

from loguru import logger

from database.db_manager import DatabaseManager
from executor.position_manager import PositionManager


class RiskManager:
    """リスク管理クラス（サーキットブレーカー内蔵）"""

    def __init__(
        self,
        risk_config: dict,
        db_manager: DatabaseManager,
        position_manager: PositionManager,
    ):
        self.db_manager = db_manager
        self.position_manager = position_manager

        global_cfg = risk_config.get("global", {})
        self.max_total_position_usdc = global_cfg.get("max_total_position_usdc", 1000)
        self.max_daily_loss_usdc = global_cfg.get("max_daily_loss_usdc", 100)
        self.max_daily_trades = global_cfg.get("max_daily_trades", 50)
        self.max_single_trade_usdc = global_cfg.get("max_single_trade_usdc", 100)

        cb_cfg = risk_config.get("circuit_breaker", {})
        self.cb_enabled = cb_cfg.get("enabled", True)
        self.cb_cooldown_minutes = cb_cfg.get("cooldown_minutes", 60)

        # サーキットブレーカー状態
        self._halted = False
        self._halted_at: datetime | None = None

        logger.info(
            f"RiskManager initialized: max_position={self.max_total_position_usdc}, "
            f"max_daily_loss={self.max_daily_loss_usdc}, "
            f"max_daily_trades={self.max_daily_trades}, "
            f"max_single_trade={self.max_single_trade_usdc}"
        )

    def check_order(self, asset_id: str, action: str, amount_usdc: float) -> bool:
        """注文のリスクチェック

        Returns:
            True: 注文可能, False: 拒否
        """
        # 1. サーキットブレーカー
        if self._check_circuit_breaker():
            logger.warning(f"[RISK] サーキットブレーカー停止中: {asset_id[:16]}...")
            return False

        # 2. 単一取引サイズ上限
        if amount_usdc > self.max_single_trade_usdc:
            logger.warning(
                f"[RISK] 単一取引サイズ超過: {amount_usdc:.2f} > {self.max_single_trade_usdc}"
            )
            return False

        # 3. 最大ポジション上限（BUYのみ）
        if action == "BUY":
            total = self.position_manager.get_total_position_usdc()
            if total + amount_usdc > self.max_total_position_usdc:
                logger.warning(
                    f"[RISK] ポジション上限超過: {total:.2f} + {amount_usdc:.2f} > "
                    f"{self.max_total_position_usdc}"
                )
                return False

        # 4. 日次取引回数上限
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        trades_today = self.db_manager.get_trades_since(today_start)
        if len(trades_today) >= self.max_daily_trades:
            logger.warning(
                f"[RISK] 日次取引上限: {len(trades_today)} >= {self.max_daily_trades}"
            )
            return False

        # 5. 日次損失上限（超過でサーキットブレーカー発動）
        daily_pnl = self.db_manager.get_daily_pnl()
        if daily_pnl < -self.max_daily_loss_usdc:
            logger.warning(
                f"[RISK] 日次損失上限超過: {daily_pnl:.2f} < -{self.max_daily_loss_usdc} → "
                f"サーキットブレーカー発動"
            )
            self._trigger_circuit_breaker()
            return False

        return True

    def _check_circuit_breaker(self) -> bool:
        """サーキットブレーカー状態を確認（クールダウン経過で自動復帰）"""
        if not self._halted:
            return False
        if not self.cb_enabled:
            return False

        elapsed = datetime.now(timezone.utc) - self._halted_at
        if elapsed >= timedelta(minutes=self.cb_cooldown_minutes):
            logger.info("[RISK] サーキットブレーカー解除（クールダウン経過）")
            self._halted = False
            self._halted_at = None
            return False

        return True

    def _trigger_circuit_breaker(self) -> None:
        """サーキットブレーカーを発動"""
        self._halted = True
        self._halted_at = datetime.now(timezone.utc)
        logger.warning(
            f"[RISK] サーキットブレーカー発動: {self.cb_cooldown_minutes}分間停止"
        )
