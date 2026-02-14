"""ポジション管理モジュール"""
from typing import Optional

from loguru import logger

from database.db_manager import DatabaseManager
from database.models import Position


class PositionManager:
    """ポジション管理クラス"""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        logger.info("PositionManager initialized")

    def get_position(self, asset_id: str) -> Optional[Position]:
        """asset_id のポジションを取得"""
        return self.db_manager.get_position(asset_id)

    def get_position_usdc(self, asset_id: str) -> float:
        """asset_id のポジションサイズ (USDC) を取得"""
        position = self.db_manager.get_position(asset_id)
        if position is None:
            return 0.0
        return position.size_usdc

    def get_total_position_usdc(self) -> float:
        """全ポジションの合計サイズ (USDC) を取得"""
        from sqlalchemy import select, func
        from database.models import Position

        with self.db_manager._session() as session:
            stmt = select(func.coalesce(func.sum(Position.size_usdc), 0.0))
            result = session.execute(stmt).scalar()
            return float(result)

    def update_after_trade(
        self,
        asset_id: str,
        market: Optional[str],
        action: str,
        price: float,
        amount_usdc: float,
    ) -> float:
        """取引後のポジション更新

        Returns:
            realized_pnl: 実現P&L（SELLの場合のみ非ゼロ）
        """
        position = self.db_manager.get_position(asset_id)
        realized_pnl = 0.0

        if action == "BUY":
            if position is None:
                # 新規ポジション
                self.db_manager.save_position(
                    asset_id=asset_id,
                    market=market,
                    side="BUY",
                    size_usdc=amount_usdc,
                    average_price=price,
                )
                logger.info(
                    f"[POSITION] 新規: {asset_id[:16]}... | "
                    f"size={amount_usdc:.2f} USDC @ {price:.4f}"
                )
            else:
                # 加重平均で追加
                total_usdc = position.size_usdc + amount_usdc
                new_avg = (
                    (position.average_price * position.size_usdc)
                    + (price * amount_usdc)
                ) / total_usdc
                self.db_manager.update_position(
                    asset_id=asset_id,
                    size_usdc=total_usdc,
                    average_price=new_avg,
                )
                logger.info(
                    f"[POSITION] 追加: {asset_id[:16]}... | "
                    f"size={total_usdc:.2f} USDC @ avg={new_avg:.4f}"
                )

        elif action == "SELL":
            if position is None or position.size_usdc <= 0:
                logger.warning(
                    f"[POSITION] SELLスキップ: ポジションなし | {asset_id[:16]}..."
                )
                return 0.0

            sell_usdc = min(amount_usdc, position.size_usdc)
            # P&L = sell_amount * (sell_price - avg_price) / avg_price
            if position.average_price > 0:
                realized_pnl = sell_usdc * (price - position.average_price) / position.average_price
            remaining = position.size_usdc - sell_usdc

            if remaining <= 0.001:
                # 全決済
                self.db_manager.update_position(
                    asset_id=asset_id,
                    size_usdc=0.0,
                    average_price=0.0,
                    realized_pnl_delta=realized_pnl,
                )
                self.db_manager.delete_position(asset_id)
                logger.info(
                    f"[POSITION] クローズ: {asset_id[:16]}... | "
                    f"pnl={realized_pnl:+.4f} USDC"
                )
            else:
                # 部分決済
                self.db_manager.update_position(
                    asset_id=asset_id,
                    size_usdc=remaining,
                    average_price=position.average_price,
                    realized_pnl_delta=realized_pnl,
                )
                logger.info(
                    f"[POSITION] 部分決済: {asset_id[:16]}... | "
                    f"remaining={remaining:.2f} USDC | pnl={realized_pnl:+.4f}"
                )

        return realized_pnl
