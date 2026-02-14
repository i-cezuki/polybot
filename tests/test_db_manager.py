"""DatabaseManagerのユニットテスト"""
from datetime import datetime, timedelta, timezone

import pytest

from database.db_manager import DatabaseManager


class TestDatabaseManager:
    @pytest.fixture
    def db(self):
        return DatabaseManager(db_path=":memory:")

    def test_save_price(self, db):
        """価格データを保存できること"""
        record_id = db.save_price(
            asset_id="token_abc",
            market="0xmarket1",
            price=0.55,
            size=100.0,
            side="BUY",
            best_bid=0.54,
            best_ask=0.56,
        )
        assert record_id > 0

    def test_get_price_history(self, db):
        """保存した価格データを取得できること"""
        now = datetime.now(timezone.utc)
        for i in range(5):
            db.save_price(
                asset_id="token_abc",
                market="0xmarket1",
                price=0.50 + i * 0.01,
                timestamp=now - timedelta(minutes=4 - i),
            )

        history = db.get_price_history(market="0xmarket1", minutes=5)
        assert len(history) == 5
        assert history[0].price == pytest.approx(0.50)
        assert history[4].price == pytest.approx(0.54)

    def test_get_price_history_empty(self, db):
        """該当マーケットの履歴がない場合、空リストを返すこと"""
        history = db.get_price_history(market="0xnonexistent", minutes=5)
        assert history == []

    def test_get_price_history_time_filter(self, db):
        """時間範囲外のデータが除外されること"""
        old_time = datetime.now(timezone.utc) - timedelta(minutes=30)
        db.save_price(
            asset_id="token_abc", market="0xmarket1",
            price=0.50, timestamp=old_time,
        )
        recent_time = datetime.now(timezone.utc) - timedelta(minutes=2)
        db.save_price(
            asset_id="token_abc", market="0xmarket1",
            price=0.55, timestamp=recent_time,
        )

        history = db.get_price_history(market="0xmarket1", minutes=5)
        assert len(history) == 1
        assert history[0].price == pytest.approx(0.55)

    def test_save_alert_log(self, db):
        """アラートログを保存できること"""
        alert_id = db.save_alert_log(
            alert_name="テストアラート",
            asset_id="token_abc",
            condition_type="price_below",
            threshold=0.10,
            current_value=0.05,
            message="テストメッセージ",
        )
        assert alert_id > 0

    def test_get_last_alert_time(self, db):
        """最終アラート時刻を取得できること"""
        db.save_alert_log(
            alert_name="テストアラート",
            asset_id="token_abc",
            condition_type="price_below",
            threshold=0.10,
            current_value=0.05,
            message="テストメッセージ",
        )

        last_time = db.get_last_alert_time("テストアラート")
        assert last_time is not None
        assert isinstance(last_time, datetime)

    def test_get_last_alert_time_none(self, db):
        """アラートログがない場合Noneを返すこと"""
        last_time = db.get_last_alert_time("存在しないアラート")
        assert last_time is None

    def test_save_notification_history(self, db):
        """通知履歴を保存できること"""
        alert_id = db.save_alert_log(
            alert_name="テストアラート",
            asset_id="token_abc",
            condition_type="price_below",
            threshold=0.10,
            current_value=0.05,
            message="テストメッセージ",
        )
        notif_id = db.save_notification_history(
            alert_log_id=alert_id,
            channel="telegram",
            status="success",
        )
        assert notif_id > 0

    def test_save_notification_history_with_error(self, db):
        """エラー付き通知履歴を保存できること"""
        notif_id = db.save_notification_history(
            alert_log_id=1,
            channel="discord",
            status="error",
            error_message="Connection timeout",
        )
        assert notif_id > 0
