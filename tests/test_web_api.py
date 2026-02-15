"""Web API テスト"""
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from web.api import app, _load_calculate_signal


@pytest.fixture
def client():
    """TestClient を返す"""
    return TestClient(app)


class TestStatusEndpoint:
    """GET /api/status テスト"""

    def test_status(self, client):
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["version"] == "1.0.0"

    def test_status_has_daily_pnl(self, client):
        """daily_pnl と total_assets_usdc が含まれること"""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "daily_pnl" in data
        assert "total_assets_usdc" in data

    def test_status_with_mock_db(self, client):
        """DB にデータがある場合の daily_pnl と total_assets_usdc"""
        import web.api as api_module

        mock_db = MagicMock()
        mock_db.get_daily_pnl.return_value = 42.5
        mock_pos = MagicMock()
        mock_pos.size_usdc = 500.0
        mock_db.get_all_positions.return_value = [mock_pos]

        original_db = api_module._db_manager
        api_module._db_manager = mock_db
        try:
            response = client.get("/api/status")
            assert response.status_code == 200
            data = response.json()
            assert data["daily_pnl"] == 42.5
            assert data["total_assets_usdc"] == 500.0
        finally:
            api_module._db_manager = original_db


class TestPositionsEndpoint:
    """GET /api/positions テスト"""

    def test_positions_empty(self, client):
        response = client.get("/api/positions")
        assert response.status_code == 200
        data = response.json()
        assert "positions" in data
        assert "total_value_usdc" in data

    def test_positions_with_data(self, client):
        """DB にポジションがある場合"""
        import web.api as api_module

        mock_db = MagicMock()
        mock_pos = MagicMock()
        mock_pos.asset_id = "asset1"
        mock_pos.market = "0xabc"
        mock_pos.side = "BUY"
        mock_pos.size_usdc = 100.0
        mock_pos.average_price = 0.50
        mock_pos.realized_pnl = 5.0
        mock_pos.opened_at = None
        mock_pos.updated_at = None
        mock_db.get_all_positions.return_value = [mock_pos]

        original_db = api_module._db_manager
        api_module._db_manager = mock_db
        try:
            response = client.get("/api/positions")
            assert response.status_code == 200
            data = response.json()
            assert len(data["positions"]) == 1
            assert data["positions"][0]["asset_id"] == "asset1"
            assert data["total_value_usdc"] == 100.0
        finally:
            api_module._db_manager = original_db


class TestTradesEndpoint:
    """GET /api/trades テスト"""

    def test_trades_empty(self, client):
        response = client.get("/api/trades")
        assert response.status_code == 200
        data = response.json()
        assert "trades" in data
        assert "count" in data

    def test_trades_with_params(self, client):
        response = client.get("/api/trades?limit=10&since_hours=48")
        assert response.status_code == 200
        data = response.json()
        assert "trades" in data


class TestPerformanceEndpoint:
    """GET /api/performance テスト"""

    def test_performance_empty(self, client):
        response = client.get("/api/performance")
        assert response.status_code == 200
        data = response.json()
        assert "total_pnl" in data
        assert "win_rate" in data
        assert "total_trades" in data

    def test_performance_with_days(self, client):
        response = client.get("/api/performance?days=30")
        assert response.status_code == 200


class TestBacktestEndpoint:
    """POST /api/backtest テスト"""

    def test_backtest_no_data(self, client):
        """データなし → エラーメッセージ"""
        response = client.post("/api/backtest?days=1")
        assert response.status_code == 200
        data = response.json()
        # 戦略ファイルがない or データがない場合はエラーを返す
        assert "error" in data or "analysis" in data

    def test_backtest_with_mock_data(self, client, tmp_path):
        """モックデータでバックテスト実行"""
        import web.api as api_module

        # JSONL データ作成
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        ticks = []
        for i in range(10):
            ticks.append(json.dumps({
                "asset_id": "asset1",
                "market": "0xtest",
                "price": str(0.20 + i * 0.05),
                "size": "100",
                "side": "BUY",
                "best_bid": str(0.19 + i * 0.05),
                "best_ask": str(0.21 + i * 0.05),
                "timestamp": f"2026-02-14T10:0{i}:00Z",
            }))

        jsonl_file = data_dir / "price_changes_2026-02-14.jsonl"
        jsonl_file.write_text("\n".join(ticks))

        # 戦略ファイル作成
        strategy_dir = tmp_path / "config"
        strategy_dir.mkdir()
        strategy_file = strategy_dir / "strategy.py"
        strategy_file.write_text(
            'def calculate_signal(data):\n'
            '    return {"action": "HOLD", "amount": 0, "reason": "test"}\n'
        )

        # DataFetcher と戦略ロードをモック
        with patch("web.api.DataFetcher") as MockFetcher, \
             patch("web.api._load_calculate_signal") as mock_load:
            mock_fetcher_instance = MockFetcher.return_value
            mock_fetcher_instance.load_jsonl_files.return_value = [
                {
                    "asset_id": "asset1",
                    "market": "0xtest",
                    "price": 0.50,
                    "timestamp": "2026-02-14T10:00:00Z",
                }
            ]
            mock_fetcher_instance.load_from_db.return_value = []

            def hold_signal(data):
                return {"action": "HOLD", "amount": 0, "reason": "test"}

            mock_load.return_value = hold_signal

            response = client.post("/api/backtest?days=7&initial_capital=10000")
            assert response.status_code == 200
            data = response.json()
            assert "analysis" in data
            assert data["analysis"]["initial_capital"] == 10000.0


class TestLoadCalculateSignal:
    """戦略ロード"""

    def test_load_existing_strategy(self, tmp_path):
        strategy_file = tmp_path / "strategy.py"
        strategy_file.write_text(
            'def calculate_signal(data):\n'
            '    return {"action": "HOLD", "amount": 0, "reason": "test"}\n'
        )

        fn = _load_calculate_signal(str(strategy_file))
        assert fn is not None
        result = fn({"price": 0.5})
        assert result["action"] == "HOLD"

    def test_load_missing_file(self):
        fn = _load_calculate_signal("/nonexistent/strategy.py")
        assert fn is None


class TestLogsEndpoint:
    """GET /api/logs テスト"""

    def test_logs_no_dir(self, client):
        """ログディレクトリが無い場合"""
        with patch("web.api.Path") as MockPath:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = False

            def side_effect(arg):
                if arg == "logs":
                    return mock_log_dir
                return Path(arg)

            MockPath.side_effect = side_effect

            response = client.get("/api/logs")
            assert response.status_code == 200
            data = response.json()
            assert data["logs"] == []
            assert data["count"] == 0

    def test_logs_with_file(self, client, tmp_path):
        """ログファイルがある場合のパース確認"""
        log_content = (
            "2026-02-15 10:00:00 | INFO     | web.api:startup_event - Web API 起動完了\n"
            "2026-02-15 10:00:01 | WARNING  | monitor:check - 価格急変\n"
            "2026-02-15 10:00:02 | ERROR    | executor:run - 注文エラー\n"
        )
        log_file = tmp_path / "polybot_2026-02-15.log"
        log_file.write_text(log_content)

        with patch("web.api.Path") as MockPath:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]

            def side_effect(arg):
                if arg == "logs":
                    return mock_log_dir
                return Path(arg)

            MockPath.side_effect = side_effect

            response = client.get("/api/logs")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 3
            assert data["logs"][0]["level"] == "INFO"
            assert data["logs"][2]["level"] == "ERROR"

    def test_logs_with_level_filter(self, client, tmp_path):
        """level パラメータでフィルタリング"""
        log_content = (
            "2026-02-15 10:00:00 | INFO     | test - info msg\n"
            "2026-02-15 10:00:01 | ERROR    | test - error msg\n"
        )
        log_file = tmp_path / "polybot_2026-02-15.log"
        log_file.write_text(log_content)

        with patch("web.api.Path") as MockPath:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]

            def side_effect(arg):
                if arg == "logs":
                    return mock_log_dir
                return Path(arg)

            MockPath.side_effect = side_effect

            response = client.get("/api/logs?level=ERROR")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1
            assert data["logs"][0]["level"] == "ERROR"

    def test_logs_with_limit(self, client, tmp_path):
        """limit パラメータで件数制限"""
        lines = []
        for i in range(10):
            lines.append(f"2026-02-15 10:00:{i:02d} | INFO     | test - msg {i}")
        log_file = tmp_path / "polybot_2026-02-15.log"
        log_file.write_text("\n".join(lines))

        with patch("web.api.Path") as MockPath:
            mock_log_dir = MagicMock()
            mock_log_dir.exists.return_value = True
            mock_log_dir.glob.return_value = [log_file]

            def side_effect(arg):
                if arg == "logs":
                    return mock_log_dir
                return Path(arg)

            MockPath.side_effect = side_effect

            response = client.get("/api/logs?limit=3")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 3
