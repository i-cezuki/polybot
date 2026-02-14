"""注文実行モジュール（Week 3: シミュレーションのみ）"""
import os
from typing import Optional

from loguru import logger

from database.db_manager import DatabaseManager


class OrderExecutor:
    """注文実行クラス

    Week 3 は全てシミュレーション（DBに Trade 記録のみ）。
    ENABLE_TRADING 環境変数で将来のライブ切替に備える。
    """

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.live_trading = os.environ.get("ENABLE_TRADING", "false").lower() == "true"
        mode = "LIVE" if self.live_trading else "SIMULATED"
        logger.info(f"OrderExecutor initialized: mode={mode}")

    def execute(
        self,
        asset_id: str,
        market: Optional[str],
        action: str,
        price: float,
        amount_usdc: float,
        reason: str = "",
    ) -> Optional[int]:
        """注文を実行（シミュレーション）

        Returns:
            Trade ID or None if failed
        """
        if self.live_trading:
            logger.warning("ライブ取引は未実装です。シミュレーションで実行します。")

        simulated = 0 if self.live_trading else 1

        trade_id = self.db_manager.save_trade(
            asset_id=asset_id,
            market=market,
            action=action,
            price=price,
            amount_usdc=amount_usdc,
            simulated=simulated,
            reason=reason,
        )

        logger.info(
            f"[TRADE-SIM] {action} {amount_usdc:.2f} USDC @ {price:.4f} | "
            f"asset={asset_id[:16]}... | reason={reason}"
        )

        return trade_id
