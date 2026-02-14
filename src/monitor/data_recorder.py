"""データ蓄積モジュール（JSONL形式）

WebSocketから受信した価格データをJSONL（1行1JSON）形式で
data/ ディレクトリに保存する。Week 4のバックテスト用データ。

ファイル構成:
  data/price_changes_YYYY-MM-DD.jsonl  - 価格変更イベント
  data/books_YYYY-MM-DD.jsonl          - オーダーブックスナップショット
  data/trades_YYYY-MM-DD.jsonl         - 取引イベント
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from loguru import logger


class DataRecorder:
    """JSONL形式でイベントデータをファイルに追記保存する"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self._file_handles: Dict[str, Any] = {}
        logger.info(f"DataRecorder 初期化完了: {self.data_dir}")

    def _get_file_path(self, prefix: str) -> Path:
        """日付ベースのファイルパスを取得"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.data_dir / f"{prefix}_{today}.jsonl"

    def _write_jsonl(self, prefix: str, record: Dict[str, Any]):
        """JSONL形式で1行追記"""
        filepath = self._get_file_path(prefix)
        record["recorded_at"] = datetime.now(timezone.utc).isoformat()
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    async def handle_event(self, event_type: str, data: Dict[str, Any]):
        """PriceMonitorから呼ばれるイベントハンドラー

        price_monitor.add_handler(recorder.handle_event) で登録する。

        Args:
            event_type: イベント種別 ("price_change", "book", "last_trade_price")
            data: イベントデータ
        """
        if event_type == "price_change":
            self._write_jsonl("price_changes", data)
        elif event_type == "book":
            self._write_jsonl("books", data)
        elif event_type == "last_trade_price":
            self._write_jsonl("trades", data)
