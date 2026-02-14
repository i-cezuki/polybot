"""データベースモデル定義（SQLAlchemy 2.x）"""
from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, Text, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PriceHistory(Base):
    """価格履歴テーブル"""
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    asset_id: Mapped[str] = mapped_column(String(256), index=True)
    market: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    size: Mapped[float | None] = mapped_column(Float, nullable=True)
    side: Mapped[str | None] = mapped_column(String(10), nullable=True)
    best_bid: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_ask: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class AlertLog(Base):
    """アラートログテーブル"""
    __tablename__ = "alert_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_name: Mapped[str] = mapped_column(String(256))
    asset_id: Mapped[str] = mapped_column(String(256))
    condition_type: Mapped[str] = mapped_column(String(64))
    threshold: Mapped[float] = mapped_column(Float)
    current_value: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(Text)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class NotificationHistory(Base):
    """通知履歴テーブル"""
    __tablename__ = "notification_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_log_id: Mapped[int] = mapped_column(Integer, index=True)
    channel: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
