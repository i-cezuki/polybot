"""WebSocket クライアント（Polymarket CLOB WebSocket対応）"""
import asyncio
import json
from typing import Callable, List, Optional

import websockets
from loguru import logger


class WebSocketClient:
    """Polymarket CLOB WebSocket クライアント"""

    PING_INTERVAL = 10  # Polymarket要件: 10秒ごとにPING送信

    def __init__(
        self,
        ws_url: str,
        on_message: Callable,
        reconnect_delay: int = 5,
        max_reconnect_attempts: int = 10,
    ):
        """
        初期化

        Args:
            ws_url: WebSocket URL
            on_message: メッセージ受信時のコールバック関数
            reconnect_delay: 再接続待機時間（秒）
            max_reconnect_attempts: 最大再接続試行回数
        """
        self.ws_url = ws_url
        self.on_message = on_message
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts

        self.websocket = None
        self.is_running = False
        self.reconnect_count = 0
        self._ping_task: Optional[asyncio.Task] = None
        self._subscribed_assets: List[str] = []

    async def connect(self):
        """WebSocket接続を確立"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            self.is_running = True
            self.reconnect_count = 0

            # PING送信タスク開始
            self._ping_task = asyncio.create_task(self._ping_loop())

            logger.info(f"WebSocket接続成功: {self.ws_url}")

        except Exception as e:
            logger.error(f"WebSocket接続失敗: {e}")
            raise

    async def subscribe_to_market(self, asset_ids: List[str]):
        """
        マーケットを購読（Polymarket CLOB WebSocket形式）

        Args:
            asset_ids: トークンIDのリスト（YesトークンID、NoトークンIDなど）
        """
        if not self.websocket:
            logger.error("WebSocketが接続されていません")
            return

        # 初回購読メッセージ
        subscribe_msg = {
            "assets_ids": asset_ids,
            "type": "market",
        }

        try:
            await self.websocket.send(json.dumps(subscribe_msg))
            self._subscribed_assets.extend(asset_ids)
            logger.info(f"マーケット購読開始: {asset_ids}")
        except Exception as e:
            logger.error(f"購読メッセージ送信失敗: {e}")

    async def unsubscribe_from_market(self, asset_ids: List[str]):
        """
        マーケットの購読を解除

        Args:
            asset_ids: トークンIDのリスト
        """
        if not self.websocket:
            return

        unsubscribe_msg = {
            "assets_ids": asset_ids,
            "operation": "unsubscribe",
        }

        try:
            await self.websocket.send(json.dumps(unsubscribe_msg))
            for aid in asset_ids:
                if aid in self._subscribed_assets:
                    self._subscribed_assets.remove(aid)
            logger.info(f"マーケット購読解除: {asset_ids}")
        except Exception as e:
            logger.error(f"購読解除メッセージ送信失敗: {e}")

    async def listen(self):
        """メッセージ受信ループ"""
        while self.is_running:
            try:
                if not self.websocket:
                    await self._reconnect()
                    continue

                message = await self.websocket.recv()

                # PONG応答は無視
                if message == "PONG":
                    continue

                data = json.loads(message)

                # コールバック関数を実行
                await self.on_message(data)

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket接続が切断されました")
                await self._reconnect()

            except json.JSONDecodeError as e:
                logger.warning(f"JSONパースエラー: {e}, message={message[:100]}")

            except Exception as e:
                logger.error(f"メッセージ受信エラー: {e}")
                await asyncio.sleep(1)

    async def _ping_loop(self):
        """定期的にPINGを送信してWebSocket接続を維持"""
        while self.is_running:
            try:
                if self.websocket:
                    await self.websocket.send("PING")
                    logger.debug("PING送信")
                await asyncio.sleep(self.PING_INTERVAL)
            except websockets.exceptions.ConnectionClosed:
                logger.warning("PING送信中にWebSocket接続が切断されました")
                break
            except Exception as e:
                logger.error(f"PING送信エラー: {e}")
                break

    async def _reconnect(self):
        """WebSocket再接続"""
        if self.reconnect_count >= self.max_reconnect_attempts:
            logger.error(
                f"最大再接続回数（{self.max_reconnect_attempts}）に達しました"
            )
            self.is_running = False
            return

        self.reconnect_count += 1
        logger.info(
            f"再接続試行 {self.reconnect_count}/{self.max_reconnect_attempts}"
        )

        await asyncio.sleep(self.reconnect_delay)

        try:
            await self.connect()

            # 再購読
            if self._subscribed_assets:
                await self.subscribe_to_market(self._subscribed_assets)

        except Exception as e:
            logger.error(f"再接続失敗: {e}")

    async def close(self):
        """WebSocket接続を閉じる"""
        self.is_running = False

        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket接続を閉じました")
