"""Discord通知モジュール"""
import os

from loguru import logger


class DiscordNotifier:
    """Discord Webhookを使用した通知クラス"""

    def __init__(self):
        self.webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")
        self.enabled = bool(self.webhook_url)

        if self.enabled:
            logger.info("Discord通知: 有効")
        else:
            logger.info("Discord通知: 無効（環境変数未設定）")

    async def send_message(
        self,
        market_name: str,
        price: str,
        condition: str,
        message: str,
    ) -> bool:
        """Discordにメッセージを送信

        Returns:
            bool: 送信成功ならTrue
        """
        if not self.enabled:
            return False

        try:
            from discord_webhook import DiscordWebhook

            content = (
                f"**[{condition}]** {market_name}\n"
                f"価格: {price}\n"
                f"{message}"
            )
            webhook = DiscordWebhook(url=self.webhook_url, content=content)
            response = webhook.execute()
            if response and response.status_code in (200, 204):
                logger.info(f"Discord通知送信成功: {condition}")
                return True
            else:
                status = response.status_code if response else "no response"
                logger.error(f"Discord通知送信失敗: status={status}")
                return False
        except Exception as e:
            logger.error(f"Discord通知送信失敗: {e}")
            return False
