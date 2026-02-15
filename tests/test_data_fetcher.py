"""DataFetcher テスト"""
import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backtester.data_fetcher import DataFetcher
from database.db_manager import DatabaseManager


# --- JSONL テストデータ ---

def _make_tick(asset_id="asset1", market="0xabc", price="0.50", timestamp="2026-02-14T10:00:00Z"):
    return {
        "asset_id": asset_id,
        "market": market,
        "price": price,
        "size": "100",
        "side": "BUY",
        "best_bid": "0.49",
        "best_ask": "0.51",
        "timestamp": timestamp,
        "recorded_at": "2026-02-14T10:00:01Z",
    }


def _write_jsonl(filepath, records):
    with open(filepath, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


class TestLoadJsonlFiles:
    """JSONL ファイルからのデータロード"""

    def test_single_file(self, tmp_path):
        ticks = [_make_tick(timestamp=f"2026-02-14T10:0{i}:00Z") for i in range(5)]
        _write_jsonl(tmp_path / "price_changes_2026-02-14.jsonl", ticks)

        fetcher = DataFetcher(data_dir=str(tmp_path))
        result = fetcher.load_jsonl_files()

        assert len(result) == 5

    def test_multiple_files(self, tmp_path):
        ticks1 = [_make_tick(timestamp="2026-02-13T10:00:00Z")]
        ticks2 = [_make_tick(timestamp="2026-02-14T10:00:00Z")]
        _write_jsonl(tmp_path / "price_changes_2026-02-13.jsonl", ticks1)
        _write_jsonl(tmp_path / "price_changes_2026-02-14.jsonl", ticks2)

        fetcher = DataFetcher(data_dir=str(tmp_path))
        result = fetcher.load_jsonl_files()

        assert len(result) == 2
        # timestamp 昇順
        assert result[0]["timestamp"] < result[1]["timestamp"]

    def test_empty_directory(self, tmp_path):
        fetcher = DataFetcher(data_dir=str(tmp_path))
        result = fetcher.load_jsonl_files()
        assert result == []


class TestNumericConversion:
    """文字列 → float 変換"""

    def test_string_to_float(self, tmp_path):
        tick = _make_tick(price="0.123", timestamp="2026-02-14T10:00:00Z")
        _write_jsonl(tmp_path / "price_changes_2026-02-14.jsonl", [tick])

        fetcher = DataFetcher(data_dir=str(tmp_path))
        result = fetcher.load_jsonl_files()

        assert isinstance(result[0]["price"], float)
        assert result[0]["price"] == 0.123
        assert isinstance(result[0]["best_bid"], float)
        assert result[0]["best_bid"] == 0.49
        assert isinstance(result[0]["best_ask"], float)
        assert result[0]["best_ask"] == 0.51
        assert isinstance(result[0]["size"], float)
        assert result[0]["size"] == 100.0


class TestFiltering:
    """market_id / asset_id / 日付フィルタ"""

    def test_market_id_filter(self, tmp_path):
        ticks = [
            _make_tick(market="0xabc", timestamp="2026-02-14T10:00:00Z"),
            _make_tick(market="0xdef", timestamp="2026-02-14T10:01:00Z"),
        ]
        _write_jsonl(tmp_path / "price_changes_2026-02-14.jsonl", ticks)

        fetcher = DataFetcher(data_dir=str(tmp_path))
        result = fetcher.load_jsonl_files(market_id="0xabc")

        assert len(result) == 1
        assert result[0]["market"] == "0xabc"

    def test_asset_id_filter(self, tmp_path):
        ticks = [
            _make_tick(asset_id="a1", timestamp="2026-02-14T10:00:00Z"),
            _make_tick(asset_id="a2", timestamp="2026-02-14T10:01:00Z"),
        ]
        _write_jsonl(tmp_path / "price_changes_2026-02-14.jsonl", ticks)

        fetcher = DataFetcher(data_dir=str(tmp_path))
        result = fetcher.load_jsonl_files(asset_id="a1")

        assert len(result) == 1
        assert result[0]["asset_id"] == "a1"

    def test_date_filter(self, tmp_path):
        _write_jsonl(
            tmp_path / "price_changes_2026-02-12.jsonl",
            [_make_tick(timestamp="2026-02-12T10:00:00Z")],
        )
        _write_jsonl(
            tmp_path / "price_changes_2026-02-13.jsonl",
            [_make_tick(timestamp="2026-02-13T10:00:00Z")],
        )
        _write_jsonl(
            tmp_path / "price_changes_2026-02-14.jsonl",
            [_make_tick(timestamp="2026-02-14T10:00:00Z")],
        )

        fetcher = DataFetcher(data_dir=str(tmp_path))
        result = fetcher.load_jsonl_files(start_date="2026-02-13", end_date="2026-02-13")

        assert len(result) == 1
        assert "2026-02-13" in result[0]["timestamp"]


class TestInvalidData:
    """不正行スキップ"""

    def test_skip_invalid_json(self, tmp_path):
        filepath = tmp_path / "price_changes_2026-02-14.jsonl"
        with open(filepath, "w") as f:
            f.write(json.dumps(_make_tick(timestamp="2026-02-14T10:00:00Z")) + "\n")
            f.write("THIS IS NOT JSON\n")
            f.write(json.dumps(_make_tick(timestamp="2026-02-14T10:01:00Z")) + "\n")

        fetcher = DataFetcher(data_dir=str(tmp_path))
        result = fetcher.load_jsonl_files()

        assert len(result) == 2

    def test_skip_empty_lines(self, tmp_path):
        filepath = tmp_path / "price_changes_2026-02-14.jsonl"
        with open(filepath, "w") as f:
            f.write(json.dumps(_make_tick(timestamp="2026-02-14T10:00:00Z")) + "\n")
            f.write("\n")
            f.write("\n")
            f.write(json.dumps(_make_tick(timestamp="2026-02-14T10:01:00Z")) + "\n")

        fetcher = DataFetcher(data_dir=str(tmp_path))
        result = fetcher.load_jsonl_files()

        assert len(result) == 2


class TestDbFallback:
    """DB フォールバック"""

    def test_load_from_db(self):
        db = DatabaseManager(":memory:")
        now = datetime.now(timezone.utc)
        db.save_price(
            asset_id="a1",
            market="0xabc",
            price=0.55,
            size=100,
            side="BUY",
            best_bid=0.54,
            best_ask=0.56,
            timestamp=now,
        )

        fetcher = DataFetcher(data_dir="/nonexistent", db_manager=db)
        result = fetcher.load_from_db("0xabc", minutes=60)

        assert len(result) == 1
        assert result[0]["price"] == 0.55
        assert result[0]["asset_id"] == "a1"

    def test_load_from_db_no_manager(self):
        fetcher = DataFetcher(data_dir="/nonexistent")
        result = fetcher.load_from_db("0xabc")
        assert result == []
