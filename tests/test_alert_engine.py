"""AlertEngineのユニットテスト"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from alerts.alert_engine import AlertEngine
from database.db_manager import DatabaseManager
from notifications.notification_manager import NotificationManager


class TestAlertEngine:
    @pytest.fixture
    def db_manager(self):
        return DatabaseManager(db_path=":memory:")

    @pytest.fixture
    def mock_notifier(self, db_manager):
        notifier = NotificationManager(db_manager=db_manager)
        notifier.send_alert = AsyncMock()
        return notifier

    @pytest.fixture
    def sample_alerts_config(self):
        return {
            "alerts": [
                {
                    "name": "テスト価格下限",
                    "market_id": "*",
                    "match_mode": "match_any",
                    "cooldown_minutes": 1,
                    "conditions": [
                        {"type": "price_below", "threshold": 0.10},
                    ],
                },
                {
                    "name": "テスト価格上限",
                    "market_id": "0xspecific",
                    "match_mode": "match_any",
                    "cooldown_minutes": 1,
                    "conditions": [
                        {"type": "price_above", "threshold": 0.90},
                    ],
                },
                {
                    "name": "テスト全条件",
                    "market_id": "*",
                    "match_mode": "match_all",
                    "cooldown_minutes": 1,
                    "conditions": [
                        {"type": "price_above", "threshold": 0.80},
                        {"type": "volume_above", "threshold": 100.0},
                    ],
                },
            ]
        }

    @pytest.fixture
    def engine(self, sample_alerts_config, db_manager, mock_notifier):
        return AlertEngine(
            alerts_config=sample_alerts_config,
            db_manager=db_manager,
            notification_manager=mock_notifier,
        )

    @pytest.mark.asyncio
    async def test_trigger_price_below(self, engine, mock_notifier):
        """price_below条件でアラートが発火すること"""
        await engine.check_alerts(
            asset_id="token_abc", market="0xmarket1", price=0.05,
        )
        mock_notifier.send_alert.assert_called_once()
        call_kwargs = mock_notifier.send_alert.call_args
        assert call_kwargs[1]["condition"] == "price_below"

    @pytest.mark.asyncio
    async def test_no_trigger_price_above_threshold(self, engine, mock_notifier):
        """price_below閾値を超えている場合アラートが発火しないこと"""
        await engine.check_alerts(
            asset_id="token_abc", market="0xmarket1", price=0.50,
        )
        mock_notifier.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_market_specific_match(self, engine, mock_notifier):
        """特定マーケット向けアラートが正しくマッチすること"""
        await engine.check_alerts(
            asset_id="token_abc", market="0xspecific", price=0.95,
        )
        mock_notifier.send_alert.assert_called()
        call_kwargs = mock_notifier.send_alert.call_args
        assert call_kwargs[1]["condition"] == "price_above"

    @pytest.mark.asyncio
    async def test_market_specific_no_match(self, engine, mock_notifier):
        """別マーケットではマーケット固有アラートが発火しないこと"""
        await engine.check_alerts(
            asset_id="token_abc", market="0xother", price=0.95,
        )
        # price_below (wildcard) は発火しない (0.95 > 0.10)
        # price_above (0xspecific) はマッチしない
        mock_notifier.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_cooldown(self, engine, db_manager, mock_notifier):
        """クールダウン期間中は同一アラートが再発火しないこと"""
        # 1回目: 発火する
        await engine.check_alerts(
            asset_id="token_abc", market="0xmarket1", price=0.05,
        )
        assert mock_notifier.send_alert.call_count == 1

        # 2回目: クールダウン中なので発火しない
        await engine.check_alerts(
            asset_id="token_abc", market="0xmarket1", price=0.05,
        )
        assert mock_notifier.send_alert.call_count == 1

    @pytest.mark.asyncio
    async def test_match_all_both_true(self, engine, mock_notifier):
        """match_allモードで全条件成立時にアラートが発火すること"""
        await engine.check_alerts(
            asset_id="token_abc", market="0xmarket1",
            price=0.85, size=200.0,
        )
        # price_below (0.85 > 0.10) は発火しない
        # match_all: price_above(0.85 > 0.80) AND volume_above(200 > 100) → 発火
        calls = mock_notifier.send_alert.call_args_list
        conditions = [c[1]["condition"] for c in calls]
        assert "price_above" in conditions or "volume_above" in conditions

    @pytest.mark.asyncio
    async def test_match_all_partial(self, engine, mock_notifier):
        """match_allモードで一部条件のみ成立時にアラートが発火しないこと"""
        await engine.check_alerts(
            asset_id="token_abc", market="0xmarket1",
            price=0.85, size=50.0,  # volume条件を満たさない
        )
        # match_all: price_above(True) AND volume_above(False) → 発火しない
        # price_below: 0.85 > 0.10 → 発火しない
        mock_notifier.send_alert.assert_not_called()
