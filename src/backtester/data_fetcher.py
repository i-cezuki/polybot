"""バックテスト用データフェッチャー

DataRecorder が出力した JSONL ファイルからティックデータをロードする。
DB フォールバックも提供。
"""
import json
from datetime import datetime, timedelta, timezone
from glob import glob
from pathlib import Path
from typing import Optional

from loguru import logger


class DataFetcher:
    """JSONL / DB からバックテスト用ティックデータを取得"""

    def __init__(self, data_dir: str = "data", db_manager=None):
        self.data_dir = Path(data_dir)
        self.db_manager = db_manager

    def load_jsonl_files(
        self,
        market_id: Optional[str] = None,
        asset_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """JSONL ファイルからティックデータをロード

        Args:
            market_id: マーケットIDでフィルタ
            asset_id: アセットIDでフィルタ
            start_date: 開始日 (YYYY-MM-DD)
            end_date: 終了日 (YYYY-MM-DD)

        Returns:
            timestamp 昇順でソートされたティックデータのリスト
        """
        pattern = str(self.data_dir / "price_changes_*.jsonl")
        files = sorted(glob(pattern))

        if not files:
            logger.warning(f"JSONL ファイルが見つかりません: {pattern}")
            return []

        # 日付フィルタ用にファイルを絞り込み
        if start_date or end_date:
            files = self._filter_files_by_date(files, start_date, end_date)

        ticks = []
        for filepath in files:
            ticks.extend(self._parse_jsonl(filepath, market_id, asset_id))

        # timestamp 昇順ソート
        ticks.sort(key=lambda t: t.get("timestamp", ""))

        logger.info(f"JSONL から {len(ticks)} 件のティックデータをロード")
        return ticks

    def load_from_db(self, market: str, minutes: int = 1440) -> list[dict]:
        """DB から価格履歴をロード（フォールバック）

        Args:
            market: マーケットID
            minutes: 取得する期間（分）

        Returns:
            ティックデータのリスト
        """
        if self.db_manager is None:
            logger.warning("db_manager が未設定のため DB ロード不可")
            return []

        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        until = datetime.now(timezone.utc)

        records = self.db_manager.get_price_history_range(market, since, until)

        ticks = []
        for r in records:
            ticks.append({
                "asset_id": r.asset_id,
                "market": r.market,
                "price": r.price,
                "size": r.size,
                "side": r.side,
                "best_bid": r.best_bid,
                "best_ask": r.best_ask,
                "timestamp": r.timestamp.isoformat() if r.timestamp else "",
            })

        logger.info(f"DB から {len(ticks)} 件のティックデータをロード")
        return ticks

    def _filter_files_by_date(
        self,
        files: list[str],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> list[str]:
        """ファイル名の日付部分でフィルタ"""
        filtered = []
        for filepath in files:
            # price_changes_YYYY-MM-DD.jsonl から日付を抽出
            filename = Path(filepath).stem  # price_changes_2026-02-14
            parts = filename.split("_")
            if len(parts) >= 3:
                file_date = parts[-1]  # YYYY-MM-DD
            else:
                filtered.append(filepath)
                continue

            if start_date and file_date < start_date:
                continue
            if end_date and file_date > end_date:
                continue
            filtered.append(filepath)

        return filtered

    def _parse_jsonl(
        self,
        filepath: str,
        market_id: Optional[str],
        asset_id: Optional[str],
    ) -> list[dict]:
        """単一 JSONL ファイルをパース"""
        ticks = []
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"不正な JSON 行をスキップ: {filepath}:{line_num}"
                        )
                        continue

                    # フィルタ
                    if market_id and record.get("market") != market_id:
                        continue
                    if asset_id and record.get("asset_id") != asset_id:
                        continue

                    # 数値フィールドを float 変換
                    record = self._convert_numeric_fields(record)
                    ticks.append(record)
        except OSError as e:
            logger.error(f"ファイル読み込みエラー: {filepath} - {e}")

        return ticks

    @staticmethod
    def _convert_numeric_fields(record: dict) -> dict:
        """文字列の数値フィールドを float に変換"""
        numeric_fields = ["price", "size", "best_bid", "best_ask"]
        for field in numeric_fields:
            if field in record and record[field] is not None:
                try:
                    record[field] = float(record[field])
                except (ValueError, TypeError):
                    pass
        return record
