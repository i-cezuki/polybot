"""Polymarket API クライアント"""
from typing import Any, Dict, List, Optional

import aiohttp
from loguru import logger
from py_clob_client.client import ClobClient

# Polymarket API endpoints
CLOB_HOST = "https://clob.polymarket.com"
GAMMA_HOST = "https://gamma-api.polymarket.com"
CHAIN_ID = 137  # Polygon mainnet


class PolymarketClient:
    """Polymarket API クライアントラッパー"""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        private_key: str,
        funder_address: str,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.private_key = private_key
        self.funder_address = funder_address

        # CLOB クライアント（読み取り専用で初期化）
        self.clob_client = ClobClient(CLOB_HOST)

        # HTTP セッション（Gamma API用）
        self._session: Optional[aiohttp.ClientSession] = None

        logger.info("Polymarket クライアント初期化完了")

    async def _get_session(self) -> aiohttp.ClientSession:
        """aiohttp セッションを取得（遅延初期化）"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def check_connection(self) -> bool:
        """CLOB APIへの接続確認"""
        try:
            result = self.clob_client.get_ok()
            logger.info(f"CLOB API接続確認: {result}")
            return result == "OK"
        except Exception as e:
            logger.error(f"CLOB API接続確認失敗: {e}")
            return False

    async def get_server_time(self) -> Optional[str]:
        """サーバー時刻を取得"""
        try:
            time = self.clob_client.get_server_time()
            logger.debug(f"サーバー時刻: {time}")
            return time
        except Exception as e:
            logger.error(f"サーバー時刻取得失敗: {e}")
            return None

    async def get_markets_from_gamma(
        self,
        active: bool = True,
        closed: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Gamma APIからマーケット一覧を取得

        Args:
            active: アクティブなマーケットのみ
            closed: クローズ済みを含む
            limit: 取得件数
            offset: オフセット

        Returns:
            List[Dict]: マーケット情報のリスト
        """
        try:
            session = await self._get_session()
            params = {
                "active": str(active).lower(),
                "closed": str(closed).lower(),
                "archived": "false",
                "limit": limit,
                "offset": offset,
            }
            async with session.get(
                f"{GAMMA_HOST}/markets", params=params
            ) as response:
                if response.status == 200:
                    markets = await response.json()
                    logger.info(f"Gamma API: {len(markets)}件のマーケット取得")
                    return markets
                else:
                    logger.error(
                        f"Gamma API エラー: status={response.status}"
                    )
                    return []
        except Exception as e:
            logger.error(f"Gamma API マーケット取得エラー: {e}")
            return []

    async def get_market_by_condition_id(
        self, condition_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Gamma APIからcondition IDでマーケット情報を取得

        Args:
            condition_id: マーケットのcondition ID

        Returns:
            Dict: マーケット情報
        """
        try:
            session = await self._get_session()
            params = {"condition_ids": condition_id}
            async with session.get(
                f"{GAMMA_HOST}/markets", params=params
            ) as response:
                if response.status == 200:
                    markets = await response.json()
                    if markets:
                        market = markets[0]
                        logger.info(
                            f"マーケット情報取得成功: {market.get('question', 'N/A')}"
                        )
                        return market
                    else:
                        logger.warning(
                            f"マーケットが見つかりません: {condition_id}"
                        )
                        return None
                else:
                    logger.error(
                        f"Gamma API エラー: status={response.status}"
                    )
                    return None
        except Exception as e:
            logger.error(f"マーケット情報取得エラー: {e}")
            return None

    async def get_orderbook(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        CLOB APIからオーダーブックを取得

        Args:
            token_id: トークンID

        Returns:
            Dict: オーダーブック情報
        """
        try:
            orderbook = self.clob_client.get_order_book(token_id)
            if orderbook:
                logger.debug(f"オーダーブック取得: token_id={token_id}")
                return orderbook
            else:
                logger.warning(f"オーダーブックが見つかりません: {token_id}")
                return None
        except Exception as e:
            logger.error(f"オーダーブック取得エラー: {e}")
            return None

    async def get_midpoint(self, token_id: str) -> Optional[float]:
        """
        ミッドポイント価格を取得

        Args:
            token_id: トークンID

        Returns:
            float: ミッドポイント価格
        """
        try:
            midpoint = self.clob_client.get_midpoint(token_id)
            if midpoint:
                price = float(midpoint.get("mid", 0))
                logger.debug(f"ミッドポイント: token_id={token_id}, price={price}")
                return price
            return None
        except Exception as e:
            logger.error(f"ミッドポイント取得エラー: {e}")
            return None

    async def get_last_trade_price(self, token_id: str) -> Optional[float]:
        """
        最終取引価格を取得

        Args:
            token_id: トークンID

        Returns:
            float: 最終取引価格
        """
        try:
            result = self.clob_client.get_last_trade_price(token_id)
            if result:
                price = float(result.get("price", 0))
                logger.debug(
                    f"最終取引価格: token_id={token_id}, price={price}"
                )
                return price
            return None
        except Exception as e:
            logger.error(f"最終取引価格取得エラー: {e}")
            return None

    async def close(self):
        """HTTPセッションを閉じる"""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("HTTPセッションを閉じました")
