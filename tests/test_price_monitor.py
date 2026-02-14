"""PriceMonitorのユニットテスト"""
import asyncio
from unittest.mock import AsyncMock

import pytest

from monitor.price_monitor import PriceMonitor


class TestPriceMonitor:
    @pytest.fixture
    def monitor(self):
        return PriceMonitor()

    @pytest.mark.asyncio
    async def test_handle_book_event(self, monitor, sample_book_event):
        """bookイベントでオーダーブックが保存されること"""
        await monitor.on_price_update([sample_book_event])

        asset_id = sample_book_event["asset_id"]
        ob = monitor.get_orderbook(asset_id)
        assert ob is not None
        assert len(ob["bids"]) == 2
        assert len(ob["asks"]) == 2
        assert ob["bids"][0]["price"] == "0.50"

    @pytest.mark.asyncio
    async def test_handle_price_change_wrapper(self, monitor, sample_price_change_event):
        """ラッパー形式のprice_changeイベントが処理されること"""
        await monitor.on_price_update(sample_price_change_event)

        asset_id = "12345678901234567890"
        price = monitor.get_current_price(asset_id)
        assert price == 0.55

    @pytest.mark.asyncio
    async def test_handle_price_change_no_asset_id(self, monitor, sample_price_change_no_asset):
        """asset_idがないprice_changeイベントでクラッシュしないこと"""
        await monitor.on_price_update(sample_price_change_no_asset)
        # エラーなく完了すればOK

    @pytest.mark.asyncio
    async def test_get_current_price_missing(self, monitor):
        """存在しないasset_idでNoneが返ること"""
        result = monitor.get_current_price("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_handler_callback_invoked(self, monitor, sample_price_change_event):
        """add_handlerで登録したハンドラーが呼ばれること"""
        mock_handler = AsyncMock()
        mock_handler.__name__ = "mock_handler"
        monitor.add_handler(mock_handler)

        await monitor.on_price_update(sample_price_change_event)

        mock_handler.assert_called_once()
        call_args = mock_handler.call_args
        assert call_args[0][0] == "price_change"
        assert call_args[0][1]["price"] == "0.55"

    @pytest.mark.asyncio
    async def test_handler_error_does_not_crash(self, monitor, sample_book_event):
        """ハンドラーがエラーを投げても他の処理が継続すること"""
        async def failing_handler(event_type, data):
            raise RuntimeError("Test error")

        failing_handler.__name__ = "failing_handler"
        monitor.add_handler(failing_handler)

        # エラーなく完了すればOK
        await monitor.on_price_update([sample_book_event])

        ob = monitor.get_orderbook(sample_book_event["asset_id"])
        assert ob is not None

    @pytest.mark.asyncio
    async def test_multiple_handlers(self, monitor, sample_price_change_event):
        """複数ハンドラーが全て呼ばれること"""
        handler1 = AsyncMock()
        handler1.__name__ = "handler1"
        handler2 = AsyncMock()
        handler2.__name__ = "handler2"

        monitor.add_handler(handler1)
        monitor.add_handler(handler2)

        await monitor.on_price_update(sample_price_change_event)

        handler1.assert_called_once()
        handler2.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_and_dict_both_work(self, monitor, sample_book_event):
        """リスト形式・dict形式の両方のデータを処理できること"""
        # リスト形式
        await monitor.on_price_update([sample_book_event])
        assert monitor.get_orderbook(sample_book_event["asset_id"]) is not None

        # dict形式（price_changesラッパー）
        price_event = {
            "market": "0xabc",
            "price_changes": [{
                "asset_id": "99999999999999999999",
                "price": "0.75",
                "size": "10",
                "side": "SELL",
                "best_bid": "0.74",
                "best_ask": "0.76",
            }],
        }
        await monitor.on_price_update(price_event)
        assert monitor.get_current_price("99999999999999999999") == 0.75
