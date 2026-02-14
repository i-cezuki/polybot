"""通知管理モジュール"""
from typing import Optional

from loguru import logger

from database.db_manager import DatabaseManager
from notifications.discord_bot import DiscordNotifier
from notifications.telegram_bot import TelegramNotifier


class NotificationManager:
    """Telegram/Discordを統合管理する通知マネージャー"""

    def __init__(
        self,
        db_manager: DatabaseManager,
        notifications_config: Optional[dict] = None,
    ):
        self.db = db_manager
        config = notifications_config or {}
        channels = config.get("channels", {})

        # Telegram
        telegram_conf = channels.get("telegram", {})
        if telegram_conf.get("enabled", False):
            self.telegram = TelegramNotifier()
        else:
            self.telegram = None

        # Discord
        discord_conf = channels.get("discord", {})
        if discord_conf.get("enabled", False):
            self.discord = DiscordNotifier()
        else:
            self.discord = None

        active = []
        if self.telegram and self.telegram.enabled:
            active.append("Telegram")
        if self.discord and self.discord.enabled:
            active.append("Discord")
        logger.info(f"NotificationManager 初期化完了: チャンネル={active or 'なし'}")

    async def send_alert(
        self,
        alert_log_id: int,
        market_name: str,
        price: str,
        condition: str,
        message: str,
    ):
        """全有効チャンネルにアラートを送信し結果をDBに保存"""
        notifiers = []
        if self.telegram and self.telegram.enabled:
            notifiers.append(("telegram", self.telegram))
        if self.discord and self.discord.enabled:
            notifiers.append(("discord", self.discord))

        if not notifiers:
            logger.debug("有効な通知チャンネルがありません")
            return

        for channel_name, notifier in notifiers:
            try:
                success = await notifier.send_message(
                    market_name=market_name,
                    price=price,
                    condition=condition,
                    message=message,
                )
                status = "success" if success else "failed"
                self.db.save_notification_history(
                    alert_log_id=alert_log_id,
                    channel=channel_name,
                    status=status,
                )
            except Exception as e:
                logger.error(f"通知送信エラー ({channel_name}): {e}")
                self.db.save_notification_history(
                    alert_log_id=alert_log_id,
                    channel=channel_name,
                    status="error",
                    error_message=str(e),
                )
