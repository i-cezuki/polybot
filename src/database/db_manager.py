"""データベース管理モジュール"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from database.models import AlertLog, Base, NotificationHistory, Position, PriceHistory, Trade


class DatabaseManager:
    """SQLiteデータベース管理クラス"""

    def __init__(self, db_path: str = "data/polybot.db"):
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{db_file}", echo=False)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine)

        logger.info(f"データベース初期化完了: {db_path}")

    @contextmanager
    def _session(self):
        """セッション管理（commit/rollback）"""
        session: Session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def save_price(
        self,
        asset_id: str,
        market: Optional[str] = None,
        price: Optional[float] = None,
        size: Optional[float] = None,
        side: Optional[str] = None,
        best_bid: Optional[float] = None,
        best_ask: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> int:
        """価格データをDBに保存"""
        with self._session() as session:
            record = PriceHistory(
                asset_id=asset_id,
                market=market,
                price=price,
                size=size,
                side=side,
                best_bid=best_bid,
                best_ask=best_ask,
                timestamp=timestamp or datetime.now(timezone.utc),
            )
            session.add(record)
            session.flush()
            return record.id

    def get_price_history(
        self,
        market: str,
        minutes: int = 5,
    ) -> list[PriceHistory]:
        """指定マーケットの直近N分間の価格履歴を取得"""
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        with self._session() as session:
            stmt = (
                select(PriceHistory)
                .where(PriceHistory.market == market)
                .where(PriceHistory.timestamp >= since)
                .order_by(PriceHistory.timestamp.asc())
            )
            results = session.execute(stmt).scalars().all()
            # detach from session
            session.expunge_all()
            return list(results)

    def save_alert_log(
        self,
        alert_name: str,
        asset_id: str,
        condition_type: str,
        threshold: float,
        current_value: float,
        message: str,
    ) -> int:
        """アラートログをDBに保存"""
        with self._session() as session:
            record = AlertLog(
                alert_name=alert_name,
                asset_id=asset_id,
                condition_type=condition_type,
                threshold=threshold,
                current_value=current_value,
                message=message,
                triggered_at=datetime.now(timezone.utc),
            )
            session.add(record)
            session.flush()
            return record.id

    def get_last_alert_time(
        self, alert_name: str, market: Optional[str] = None
    ) -> Optional[datetime]:
        """指定アラートの最終発火時刻を取得"""
        with self._session() as session:
            stmt = (
                select(AlertLog.triggered_at)
                .where(AlertLog.alert_name == alert_name)
                .order_by(AlertLog.triggered_at.desc())
                .limit(1)
            )
            result = session.execute(stmt).scalar_one_or_none()
            return result

    def save_notification_history(
        self,
        alert_log_id: int,
        channel: str,
        status: str,
        error_message: Optional[str] = None,
    ) -> int:
        """通知履歴をDBに保存"""
        with self._session() as session:
            record = NotificationHistory(
                alert_log_id=alert_log_id,
                channel=channel,
                status=status,
                error_message=error_message,
                sent_at=datetime.now(timezone.utc),
            )
            session.add(record)
            session.flush()
            return record.id

    # --- Trade メソッド ---

    def save_trade(
        self,
        asset_id: str,
        market: Optional[str],
        action: str,
        price: float,
        amount_usdc: float,
        simulated: int = 1,
        realized_pnl: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> int:
        """取引記録をDBに保存"""
        with self._session() as session:
            record = Trade(
                asset_id=asset_id,
                market=market,
                action=action,
                price=round(price, 6),
                amount_usdc=round(amount_usdc, 6),
                simulated=simulated,
                realized_pnl=round(realized_pnl, 6) if realized_pnl is not None else None,
                reason=reason,
                created_at=datetime.now(timezone.utc),
            )
            session.add(record)
            session.flush()
            return record.id

    def get_trades_since(self, since: datetime) -> list[Trade]:
        """指定時刻以降の取引記録を取得"""
        with self._session() as session:
            stmt = (
                select(Trade)
                .where(Trade.created_at >= since)
                .order_by(Trade.created_at.asc())
            )
            results = session.execute(stmt).scalars().all()
            session.expunge_all()
            return list(results)

    def get_daily_pnl(self) -> float:
        """本日のシミュレーション実現P&Lの合計を取得"""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        with self._session() as session:
            stmt = (
                select(func.coalesce(func.sum(Trade.realized_pnl), 0.0))
                .where(Trade.created_at >= today_start)
            )
            result = session.execute(stmt).scalar()
            return float(result)

    # --- Position メソッド ---

    def get_position(self, asset_id: str) -> Optional[Position]:
        """asset_id のポジションを取得"""
        with self._session() as session:
            stmt = select(Position).where(Position.asset_id == asset_id)
            result = session.execute(stmt).scalar_one_or_none()
            if result:
                session.expunge(result)
            return result

    def save_position(
        self,
        asset_id: str,
        market: Optional[str],
        side: str,
        size_usdc: float,
        average_price: float,
    ) -> int:
        """新規ポジションをDBに保存"""
        with self._session() as session:
            record = Position(
                asset_id=asset_id,
                market=market,
                side=side,
                size_usdc=round(size_usdc, 6),
                average_price=round(average_price, 6),
                realized_pnl=0.0,
                opened_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(record)
            session.flush()
            return record.id

    def update_position(
        self,
        asset_id: str,
        size_usdc: float,
        average_price: float,
        realized_pnl_delta: float = 0.0,
    ) -> None:
        """ポジションを更新"""
        with self._session() as session:
            stmt = select(Position).where(Position.asset_id == asset_id)
            position = session.execute(stmt).scalar_one_or_none()
            if position:
                position.size_usdc = round(size_usdc, 6)
                position.average_price = round(average_price, 6)
                position.realized_pnl = round(position.realized_pnl + realized_pnl_delta, 6)
                position.updated_at = datetime.now(timezone.utc)

    def get_all_positions(self) -> list[Position]:
        """size_usdc > 0 のポジション全取得（Web API 用）"""
        with self._session() as session:
            stmt = (
                select(Position)
                .where(Position.size_usdc > 0)
                .order_by(Position.updated_at.desc())
            )
            results = session.execute(stmt).scalars().all()
            session.expunge_all()
            return list(results)

    def get_price_history_range(
        self,
        market: str,
        since: datetime,
        until: datetime,
    ) -> list[PriceHistory]:
        """期間指定の価格履歴取得（バックテスト用）"""
        with self._session() as session:
            stmt = (
                select(PriceHistory)
                .where(PriceHistory.market == market)
                .where(PriceHistory.timestamp >= since)
                .where(PriceHistory.timestamp <= until)
                .order_by(PriceHistory.timestamp.asc())
            )
            results = session.execute(stmt).scalars().all()
            session.expunge_all()
            return list(results)

    def delete_position(self, asset_id: str) -> None:
        """ポジションを削除"""
        with self._session() as session:
            stmt = select(Position).where(Position.asset_id == asset_id)
            position = session.execute(stmt).scalar_one_or_none()
            if position:
                session.delete(position)
