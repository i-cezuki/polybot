"""Polymarket API接続テスト（統合テスト）

このテストは実際のPolymarket APIに接続するため、
環境変数が設定されている場合のみ実行される。

実行方法:
  pytest tests/test_connection.py -v
"""
import os

import pytest

# 環境変数が未設定なら統合テストをスキップ
requires_api = pytest.mark.skipif(
    not os.getenv("POLYMARKET_API_KEY"),
    reason="POLYMARKET_API_KEY が未設定（統合テストをスキップ）",
)


@requires_api
class TestConnection:
    @pytest.fixture
    def poly_client(self):
        from api.polymarket_client import PolymarketClient

        return PolymarketClient(
            api_key=os.getenv("POLYMARKET_API_KEY", ""),
            api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
            api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE", ""),
            private_key=os.getenv("POLYMARKET_PRIVATE_KEY", ""),
            funder_address=os.getenv("POLYMARKET_FUNDER_ADDRESS", ""),
        )

    @pytest.mark.asyncio
    async def test_clob_api_ok(self, poly_client):
        """CLOB APIに接続できること"""
        result = await poly_client.check_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_server_time(self, poly_client):
        """サーバー時刻を取得できること"""
        time = await poly_client.get_server_time()
        assert time is not None

    @pytest.mark.asyncio
    async def test_gamma_api_markets(self, poly_client):
        """Gamma APIからマーケット一覧を取得できること"""
        markets = await poly_client.get_markets_from_gamma(limit=5)
        assert len(markets) > 0
        assert "question" in markets[0]
        await poly_client.close()
