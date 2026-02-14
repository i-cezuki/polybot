"""pytest共通フィクスチャ"""
import sys
from pathlib import Path

import pytest

# src をインポートパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def sample_book_event():
    """bookイベントのサンプルデータ"""
    return {
        "event_type": "book",
        "asset_id": "12345678901234567890",
        "market": "0xabc123",
        "timestamp": "1771038868751",
        "bids": [
            {"price": "0.50", "size": "100"},
            {"price": "0.49", "size": "200"},
        ],
        "asks": [
            {"price": "0.51", "size": "150"},
            {"price": "0.52", "size": "300"},
        ],
    }


@pytest.fixture
def sample_price_change_event():
    """price_changeイベントのサンプルデータ（ラッパー形式）"""
    return {
        "market": "0xabc123",
        "price_changes": [
            {
                "asset_id": "12345678901234567890",
                "price": "0.55",
                "size": "500",
                "side": "BUY",
                "hash": "abc123",
                "best_bid": "0.54",
                "best_ask": "0.56",
            },
        ],
    }


@pytest.fixture
def sample_price_change_no_asset():
    """asset_idが欠落したprice_changeイベント"""
    return {
        "market": "0xabc123",
        "price_changes": [
            {
                "price": "0.55",
                "size": "500",
                "side": "BUY",
            },
        ],
    }
