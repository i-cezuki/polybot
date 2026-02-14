"""Telegram通知モジュール"""
import os

from loguru import logger


class TelegramNotifier:
    """Telegram Bot APIを使用した通知クラス"""

    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.bot_token and self.chat_id)

        if self.enabled:
            logger.info("Telegram通知: 有効")
        else:
            logger.info("Telegram通知: 無効（環境変数未設定）")

    async def send_message(
        self,
        market_name: str,
        price: str,
        condition: str,
        message: str,
    ) -> bool:
        """Telegramにメッセージを送信

        Returns:
            bool: 送信成功ならTrue
        """
        if not self.enabled:
            return False

        try:
            from telegram import Bot

            bot = Bot(token=self.bot_token)
            text = (
                f"[{condition}] {market_name}\n"
                f"価格: {price}\n"
                f"{message}"
            )
            await bot.send_message(chat_id=self.chat_id, text=text)
            logger.info(f"Telegram通知送信成功: {condition}")
            return True
        except Exception as e:
            logger.error(f"Telegram通知送信失敗: {e}")
            return False
