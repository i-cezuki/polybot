"""DataRecorderのユニットテスト"""
import json
from pathlib import Path

import pytest

from monitor.data_recorder import DataRecorder


class TestDataRecorder:
    @pytest.fixture
    def recorder(self, tmp_path):
        return DataRecorder(data_dir=str(tmp_path))

    @pytest.mark.asyncio
    async def test_price_change_saved(self, recorder, tmp_path):
        """price_changeイベントがJSONLファイルに保存されること"""
        data = {
            "asset_id": "12345",
            "market": "0xabc",
            "price": "0.55",
            "size": "100",
            "side": "BUY",
            "best_bid": "0.54",
            "best_ask": "0.56",
            "timestamp": "2026-02-14T00:00:00Z",
        }

        await recorder.handle_event("price_change", data)

        files = list(tmp_path.glob("price_changes_*.jsonl"))
        assert len(files) == 1

        with open(files[0]) as f:
            line = f.readline()
            record = json.loads(line)

        assert record["asset_id"] == "12345"
        assert record["price"] == "0.55"
        assert "recorded_at" in record

    @pytest.mark.asyncio
    async def test_book_saved(self, recorder, tmp_path):
        """bookイベントがJSONLファイルに保存されること"""
        data = {
            "asset_id": "12345",
            "market": "0xabc",
            "timestamp": "1234567890",
            "best_bid": "0.50",
            "best_ask": "0.51",
            "bids_count": 10,
            "asks_count": 15,
        }

        await recorder.handle_event("book", data)

        files = list(tmp_path.glob("books_*.jsonl"))
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_trade_saved(self, recorder, tmp_path):
        """last_trade_priceイベントがJSONLファイルに保存されること"""
        data = {
            "asset_id": "12345",
            "price": "0.60",
            "size": "50",
            "side": "SELL",
        }

        await recorder.handle_event("last_trade_price", data)

        files = list(tmp_path.glob("trades_*.jsonl"))
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_multiple_records_appended(self, recorder, tmp_path):
        """複数レコードが同一ファイルに追記されること"""
        for i in range(3):
            await recorder.handle_event("price_change", {
                "asset_id": f"token_{i}",
                "price": str(0.5 + i * 0.1),
            })

        files = list(tmp_path.glob("price_changes_*.jsonl"))
        assert len(files) == 1

        with open(files[0]) as f:
            lines = f.readlines()
        assert len(lines) == 3
