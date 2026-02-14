"""データベース管理モジュール"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from loguru import logger
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from database.models import AlertLog, Base, NotificationHistory, PriceHistory


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
