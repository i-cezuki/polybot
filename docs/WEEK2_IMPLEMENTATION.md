# PolyBot Framework - Week 2 実装設計書

## 📋 Week 2 の目標

**監視エンジンと通知機能の実装**

### 成果物
- アラート条件の設定機能
- Telegram/Discord通知の実装
- 価格監視ダッシュボード（簡易版）
- 監視ログのデータベース保存

---

## 🏗️ 追加ファイル構成

```
polybot-framework/
├── config/
│   ├── alerts.yaml          # NEW: アラート設定
│   └── notifications.yaml   # NEW: 通知設定
├── src/
│   ├── alerts/
│   │   ├── __init__.py
│   │   ├── alert_engine.py      # NEW: アラートエンジン
│   │   └── conditions.py        # NEW: 条件判定ロジック
│   ├── notifications/
│   │   ├── __init__.py
│   │   ├── telegram_bot.py      # NEW: Telegram通知
│   │   └── discord_bot.py       # NEW: Discord通知
│   └── database/
│       ├── __init__.py
│       ├── db_manager.py        # NEW: DB管理
│       └── models.py            # NEW: データモデル
└── data/
    └── polybot.db               # NEW: SQLiteデータベース
```

---

## 📦 追加依存パッケージ

### requirements.txt に追加

```txt
# 通知
python-telegram-bot==20.7
discord-webhook==1.3.0

# データベース
sqlalchemy==2.0.23
alembic==1.13.0

# データ処理
pandas==2.1.4
```

---

## 📝 設定ファイル

### config/alerts.yaml

```yaml
# アラート設定
alerts:
  # アラート1: 価格が閾値を下回った時
  - id: "alert_001"
    name: "低価格アラート"
    market_id: "0x1234567890abcdef"
    enabled: true
    conditions:
      - type: "price_below"
        threshold: 0.30
        message: "⚠️ 価格が0.30を下回りました！買いチャンス？"
    notifications:
      telegram: true
      discord: true
    cooldown_minutes: 5  # 同じアラートの再送信を5分間抑制

  # アラート2: 価格が閾値を上回った時
  - id: "alert_002"
    name: "高価格アラート"
    market_id: "0x1234567890abcdef"
    enabled: true
    conditions:
      - type: "price_above"
        threshold: 0.70
        message: "🚀 価格が0.70を超えました！売りチャンス？"
    notifications:
      telegram: true
      discord: false
    cooldown_minutes: 5

  # アラート3: 価格変動率（1時間で5%以上変動）
  - id: "alert_003"
    name: "価格急変アラート"
    market_id: "0x1234567890abcdef"
    enabled: true
    conditions:
      - type: "price_change_percent"
        timeframe_minutes: 60
        threshold_percent: 5.0
        message: "📊 1時間で5%以上の価格変動を検出！"
    notifications:
      telegram: true
      discord: true
    cooldown_minutes: 10

  # アラート4: 複合条件（価格 AND 出来高）
  - id: "alert_004"
    name: "価格+出来高アラート"
    market_id: "0x1234567890abcdef"
    enabled: false  # 無効化
    conditions:
      - type: "price_below"
        threshold: 0.25
      - type: "volume_above"
        threshold: 100000  # USDC
        message: "💰 低価格 + 高出来高を検出！"
    match_all: true  # 全条件を満たす必要がある（AND条件）
    notifications:
      telegram: true
      discord: true
    cooldown_minutes: 15
```

### config/notifications.yaml

```yaml
# 通知設定
telegram:
  enabled: true
  bot_token: "${TELEGRAM_BOT_TOKEN}"  # 環境変数から取得
  chat_id: "${TELEGRAM_CHAT_ID}"
  
  # メッセージフォーマット
  message_format: |
    🤖 *PolyBot Alert*
    
    📍 Market: {market_name}
    💰 Price: {price}
    📊 Condition: {condition}
    
    {message}
    
    🕐 Time: {timestamp}

discord:
  enabled: false
  webhook_url: "${DISCORD_WEBHOOK_URL}"
  
  # メッセージフォーマット
  message_format: |
    **PolyBot Alert**
    
    Market: {market_name}
    Price: {price}
    Condition: {condition}
    
    {message}
    
    Time: {timestamp}
```

---

## 💻 コア実装

### src/database/models.py

```python
"""データベースモデル定義"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class PriceHistory(Base):
    """価格履歴テーブル"""
    __tablename__ = 'price_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    market_id = Column(String(100), nullable=False, index=True)
    market_name = Column(String(200))
    price = Column(Float, nullable=False)
    volume = Column(Float)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<PriceHistory(market_id={self.market_id}, price={self.price}, timestamp={self.timestamp})>"

class AlertLog(Base):
    """アラートログテーブル"""
    __tablename__ = 'alert_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(String(50), nullable=False, index=True)
    market_id = Column(String(100), nullable=False)
    condition_type = Column(String(50), nullable=False)
    threshold = Column(Float)
    current_value = Column(Float, nullable=False)
    message = Column(Text)
    triggered_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    notified = Column(Boolean, default=False)
    notification_channels = Column(String(100))  # "telegram,discord"
    
    def __repr__(self):
        return f"<AlertLog(alert_id={self.alert_id}, condition={self.condition_type}, triggered_at={self.triggered_at})>"

class NotificationHistory(Base):
    """通知履歴テーブル"""
    __tablename__ = 'notification_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_log_id = Column(Integer, nullable=False)
    channel = Column(String(20), nullable=False)  # "telegram" or "discord"
    status = Column(String(20), nullable=False)  # "success" or "failed"
    error_message = Column(Text)
    sent_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<NotificationHistory(channel={self.channel}, status={self.status}, sent_at={self.sent_at})>"
```

### src/database/db_manager.py

```python
"""データベース管理"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import List, Optional
from datetime import datetime, timedelta
from loguru import logger
from .models import Base, PriceHistory, AlertLog, NotificationHistory

class DatabaseManager:
    """データベース管理クラス"""
    
    def __init__(self, db_path: str = "data/polybot.db"):
        """
        初期化
        
        Args:
            db_path: SQLiteデータベースファイルパス
        """
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info(f"データベース初期化完了: {db_path}")
    
    @contextmanager
    def get_session(self) -> Session:
        """セッションコンテキストマネージャー"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"データベースエラー: {e}")
            raise
        finally:
            session.close()
    
    def save_price(self, market_id: str, market_name: str, price: float, 
                   volume: Optional[float] = None):
        """
        価格データを保存
        
        Args:
            market_id: マーケットID
            market_name: マーケット名
            price: 価格
            volume: 出来高
        """
        with self.get_session() as session:
            price_record = PriceHistory(
                market_id=market_id,
                market_name=market_name,
                price=price,
                volume=volume,
                timestamp=datetime.utcnow()
            )
            session.add(price_record)
            logger.debug(f"価格保存: {market_id} = {price}")
    
    def get_price_history(self, market_id: str, hours: int = 24) -> List[PriceHistory]:
        """
        価格履歴を取得
        
        Args:
            market_id: マーケットID
            hours: 過去何時間分を取得するか
            
        Returns:
            List[PriceHistory]: 価格履歴
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self.get_session() as session:
            return session.query(PriceHistory).filter(
                PriceHistory.market_id == market_id,
                PriceHistory.timestamp >= cutoff_time
            ).order_by(PriceHistory.timestamp.desc()).all()
    
    def save_alert_log(self, alert_id: str, market_id: str, condition_type: str,
                       threshold: float, current_value: float, message: str,
                       notification_channels: List[str]) -> int:
        """
        アラートログを保存
        
        Args:
            alert_id: アラートID
            market_id: マーケットID
            condition_type: 条件タイプ
            threshold: 閾値
            current_value: 現在値
            message: メッセージ
            notification_channels: 通知チャンネルリスト
            
        Returns:
            int: 保存されたレコードのID
        """
        with self.get_session() as session:
            alert_log = AlertLog(
                alert_id=alert_id,
                market_id=market_id,
                condition_type=condition_type,
                threshold=threshold,
                current_value=current_value,
                message=message,
                triggered_at=datetime.utcnow(),
                notified=False,
                notification_channels=",".join(notification_channels)
            )
            session.add(alert_log)
            session.flush()
            return alert_log.id
    
    def save_notification_history(self, alert_log_id: int, channel: str, 
                                   status: str, error_message: Optional[str] = None):
        """
        通知履歴を保存
        
        Args:
            alert_log_id: アラートログID
            channel: 通知チャンネル
            status: ステータス（success/failed）
            error_message: エラーメッセージ（失敗時）
        """
        with self.get_session() as session:
            notification = NotificationHistory(
                alert_log_id=alert_log_id,
                channel=channel,
                status=status,
                error_message=error_message,
                sent_at=datetime.utcnow()
            )
            session.add(notification)
            logger.debug(f"通知履歴保存: {channel} - {status}")
    
    def get_last_alert_time(self, alert_id: str) -> Optional[datetime]:
        """
        最後にアラートが発火した時刻を取得
        
        Args:
            alert_id: アラートID
            
        Returns:
            Optional[datetime]: 最終発火時刻
        """
        with self.get_session() as session:
            last_alert = session.query(AlertLog).filter(
                AlertLog.alert_id == alert_id
            ).order_by(AlertLog.triggered_at.desc()).first()
            
            return last_alert.triggered_at if last_alert else None
```

### src/alerts/conditions.py

```python
"""アラート条件判定ロジック"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from loguru import logger

class ConditionChecker:
    """条件チェッカー"""
    
    def __init__(self, db_manager):
        """
        初期化
        
        Args:
            db_manager: DatabaseManagerインスタンス
        """
        self.db = db_manager
    
    def check_price_below(self, market_id: str, current_price: float, 
                          threshold: float) -> bool:
        """
        価格が閾値を下回っているかチェック
        
        Args:
            market_id: マーケットID
            current_price: 現在価格
            threshold: 閾値
            
        Returns:
            bool: 条件を満たすか
        """
        result = current_price < threshold
        logger.debug(f"price_below check: {current_price} < {threshold} = {result}")
        return result
    
    def check_price_above(self, market_id: str, current_price: float, 
                          threshold: float) -> bool:
        """
        価格が閾値を上回っているかチェック
        
        Args:
            market_id: マーケットID
            current_price: 現在価格
            threshold: 閾値
            
        Returns:
            bool: 条件を満たすか
        """
        result = current_price > threshold
        logger.debug(f"price_above check: {current_price} > {threshold} = {result}")
        return result
    
    def check_price_change_percent(self, market_id: str, current_price: float,
                                    timeframe_minutes: int, threshold_percent: float) -> bool:
        """
        価格変動率をチェック
        
        Args:
            market_id: マーケットID
            current_price: 現在価格
            timeframe_minutes: 時間枠（分）
            threshold_percent: 閾値（%）
            
        Returns:
            bool: 条件を満たすか
        """
        # 過去の価格を取得
        hours = max(1, timeframe_minutes // 60)
        price_history = self.db.get_price_history(market_id, hours=hours)
        
        if not price_history:
            logger.warning(f"価格履歴がありません: {market_id}")
            return False
        
        # 指定時間前の価格を取得
        cutoff_time = datetime.utcnow() - timedelta(minutes=timeframe_minutes)
        past_prices = [p for p in price_history if p.timestamp <= cutoff_time]
        
        if not past_prices:
            logger.debug("指定時間前の価格データが不足")
            return False
        
        past_price = past_prices[0].price
        change_percent = abs((current_price - past_price) / past_price * 100)
        
        result = change_percent >= threshold_percent
        logger.debug(f"price_change check: {change_percent:.2f}% >= {threshold_percent}% = {result}")
        return result
    
    def check_volume_above(self, market_id: str, current_volume: float, 
                           threshold: float) -> bool:
        """
        出来高が閾値を上回っているかチェック
        
        Args:
            market_id: マーケットID
            current_volume: 現在出来高
            threshold: 閾値
            
        Returns:
            bool: 条件を満たすか
        """
        if current_volume is None:
            return False
        
        result = current_volume > threshold
        logger.debug(f"volume_above check: {current_volume} > {threshold} = {result}")
        return result
```

### src/alerts/alert_engine.py

```python
"""アラートエンジン"""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
from .conditions import ConditionChecker

class AlertEngine:
    """アラートエンジン"""
    
    def __init__(self, alerts_config: List[Dict], db_manager, notification_manager):
        """
        初期化
        
        Args:
            alerts_config: アラート設定リスト
            db_manager: DatabaseManagerインスタンス
            notification_manager: NotificationManagerインスタンス
        """
        self.alerts_config = alerts_config
        self.db = db_manager
        self.notifier = notification_manager
        self.condition_checker = ConditionChecker(db_manager)
        
        logger.info(f"アラートエンジン初期化: {len(alerts_config)} 件のアラート")
    
    async def check_alerts(self, market_id: str, market_name: str, 
                          current_price: float, current_volume: Optional[float] = None):
        """
        アラート条件をチェック
        
        Args:
            market_id: マーケットID
            market_name: マーケット名
            current_price: 現在価格
            current_volume: 現在出来高
        """
        for alert in self.alerts_config:
            # 無効化されているアラートはスキップ
            if not alert.get("enabled", True):
                continue
            
            # 対象マーケットでない場合はスキップ
            if alert["market_id"] != market_id:
                continue
            
            # クールダウン期間中かチェック
            if self._is_in_cooldown(alert):
                continue
            
            # 条件判定
            if await self._check_conditions(alert, market_id, current_price, current_volume):
                await self._trigger_alert(alert, market_id, market_name, current_price)
    
    def _is_in_cooldown(self, alert: Dict) -> bool:
        """
        クールダウン期間中かチェック
        
        Args:
            alert: アラート設定
            
        Returns:
            bool: クールダウン期間中か
        """
        cooldown_minutes = alert.get("cooldown_minutes", 0)
        if cooldown_minutes == 0:
            return False
        
        last_alert_time = self.db.get_last_alert_time(alert["id"])
        if last_alert_time is None:
            return False
        
        time_since_last = datetime.utcnow() - last_alert_time
        is_cooldown = time_since_last < timedelta(minutes=cooldown_minutes)
        
        if is_cooldown:
            logger.debug(f"アラート {alert['id']} はクールダウン期間中")
        
        return is_cooldown
    
    async def _check_conditions(self, alert: Dict, market_id: str, 
                                current_price: float, current_volume: Optional[float]) -> bool:
        """
        条件をチェック
        
        Args:
            alert: アラート設定
            market_id: マーケットID
            current_price: 現在価格
            current_volume: 現在出来高
            
        Returns:
            bool: 全条件を満たすか
        """
        conditions = alert.get("conditions", [])
        match_all = alert.get("match_all", True)  # デフォルトはAND条件
        
        results = []
        
        for condition in conditions:
            condition_type = condition["type"]
            
            if condition_type == "price_below":
                result = self.condition_checker.check_price_below(
                    market_id, current_price, condition["threshold"]
                )
            
            elif condition_type == "price_above":
                result = self.condition_checker.check_price_above(
                    market_id, current_price, condition["threshold"]
                )
            
            elif condition_type == "price_change_percent":
                result = self.condition_checker.check_price_change_percent(
                    market_id, current_price, 
                    condition["timeframe_minutes"], condition["threshold_percent"]
                )
            
            elif condition_type == "volume_above":
                result = self.condition_checker.check_volume_above(
                    market_id, current_volume or 0, condition["threshold"]
                )
            
            else:
                logger.warning(f"未知の条件タイプ: {condition_type}")
                result = False
            
            results.append(result)
        
        # AND条件 or OR条件
        if match_all:
            return all(results)
        else:
            return any(results)
    
    async def _trigger_alert(self, alert: Dict, market_id: str, 
                            market_name: str, current_price: float):
        """
        アラートを発火
        
        Args:
            alert: アラート設定
            market_id: マーケットID
            market_name: マーケット名
            current_price: 現在価格
        """
        logger.info(f"🚨 アラート発火: {alert['name']}")
        
        # メッセージ取得（最初の条件のメッセージを使用）
        message = alert["conditions"][0].get("message", "アラート条件を満たしました")
        
        # 通知チャンネル取得
        notifications = alert.get("notifications", {})
        channels = []
        if notifications.get("telegram"):
            channels.append("telegram")
        if notifications.get("discord"):
            channels.append("discord")
        
        # アラートログ保存
        alert_log_id = self.db.save_alert_log(
            alert_id=alert["id"],
            market_id=market_id,
            condition_type=alert["conditions"][0]["type"],
            threshold=alert["conditions"][0].get("threshold", 0),
            current_value=current_price,
            message=message,
            notification_channels=channels
        )
        
        # 通知送信
        await self.notifier.send_alert(
            alert_log_id=alert_log_id,
            market_name=market_name,
            price=current_price,
            condition=alert["conditions"][0]["type"],
            message=message,
            channels=channels
        )
```

### src/notifications/telegram_bot.py

```python
"""Telegram通知"""
from telegram import Bot
from telegram.error import TelegramError
from loguru import logger
from typing import Optional

class TelegramNotifier:
    """Telegram通知クラス"""
    
    def __init__(self, bot_token: str, chat_id: str, message_format: str):
        """
        初期化
        
        Args:
            bot_token: Telegram Bot Token
            chat_id: 送信先Chat ID
            message_format: メッセージフォーマット
        """
        self.bot = Bot(token=bot_token)
        self.chat_id = chat_id
        self.message_format = message_format
        logger.info("Telegram通知初期化完了")
    
    async def send_message(self, market_name: str, price: float, 
                          condition: str, message: str) -> bool:
        """
        メッセージ送信
        
        Args:
            market_name: マーケット名
            price: 価格
            condition: 条件タイプ
            message: メッセージ
            
        Returns:
            bool: 送信成功
        """
        try:
            formatted_message = self.message_format.format(
                market_name=market_name,
                price=price,
                condition=condition,
                message=message,
                timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            )
            
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=formatted_message,
                parse_mode="Markdown"
            )
            
            logger.info(f"✅ Telegram通知送信成功: {market_name}")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Telegram通知送信失敗: {e}")
            return False
```

### src/notifications/discord_bot.py

```python
"""Discord通知"""
from discord_webhook import DiscordWebhook
from loguru import logger
from datetime import datetime

class DiscordNotifier:
    """Discord通知クラス"""
    
    def __init__(self, webhook_url: str, message_format: str):
        """
        初期化
        
        Args:
            webhook_url: Discord Webhook URL
            message_format: メッセージフォーマット
        """
        self.webhook_url = webhook_url
        self.message_format = message_format
        logger.info("Discord通知初期化完了")
    
    async def send_message(self, market_name: str, price: float, 
                          condition: str, message: str) -> bool:
        """
        メッセージ送信
        
        Args:
            market_name: マーケット名
            price: 価格
            condition: 条件タイプ
            message: メッセージ
            
        Returns:
            bool: 送信成功
        """
        try:
            formatted_message = self.message_format.format(
                market_name=market_name,
                price=price,
                condition=condition,
                message=message,
                timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            )
            
            webhook = DiscordWebhook(url=self.webhook_url, content=formatted_message)
            response = webhook.execute()
            
            if response.status_code == 200:
                logger.info(f"✅ Discord通知送信成功: {market_name}")
                return True
            else:
                logger.error(f"❌ Discord通知送信失敗: status={response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Discord通知送信エラー: {e}")
            return False
```

### src/main.py（Week 2版に更新）

```python
"""メインエントリーポイント（Week 2版）"""
import asyncio
from loguru import logger
from utils.logger import setup_logger
from utils.config_loader import ConfigLoader
from api.polymarket_client import PolymarketClient
from api.websocket_client import WebSocketClient
from monitor.price_monitor import PriceMonitor
from database.db_manager import DatabaseManager
from alerts.alert_engine import AlertEngine
from notifications.telegram_bot import TelegramNotifier
from notifications.discord_bot import DiscordNotifier
import os

class NotificationManager:
    """通知管理クラス"""
    
    def __init__(self, telegram_config: dict, discord_config: dict, db_manager):
        self.telegram = None
        self.discord = None
        self.db = db_manager
        
        if telegram_config.get("enabled"):
            self.telegram = TelegramNotifier(
                bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
                chat_id=os.getenv("TELEGRAM_CHAT_ID"),
                message_format=telegram_config["message_format"]
            )
        
        if discord_config.get("enabled"):
            self.discord = DiscordNotifier(
                webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
                message_format=discord_config["message_format"]
            )
    
    async def send_alert(self, alert_log_id: int, market_name: str, price: float,
                        condition: str, message: str, channels: list):
        """アラート通知送信"""
        for channel in channels:
            success = False
            error_msg = None
            
            try:
                if channel == "telegram" and self.telegram:
                    success = await self.telegram.send_message(
                        market_name, price, condition, message
                    )
                elif channel == "discord" and self.discord:
                    success = await self.discord.send_message(
                        market_name, price, condition, message
                    )
            except Exception as e:
                error_msg = str(e)
                logger.error(f"通知送信エラー ({channel}): {e}")
            
            # 通知履歴保存
            self.db.save_notification_history(
                alert_log_id=alert_log_id,
                channel=channel,
                status="success" if success else "failed",
                error_message=error_msg
            )

async def main():
    """メイン処理（Week 2版）"""
    
    setup_logger("INFO")
    logger.info("=== PolyBot Framework Week 2 起動 ===")
    
    try:
        # 設定読み込み
        config_loader = ConfigLoader()
        config = config_loader.load_yaml("config.yaml")
        markets_config = config_loader.load_yaml("markets.yaml")
        alerts_config = config_loader.load_yaml("alerts.yaml")
        notifications_config = config_loader.load_yaml("notifications.yaml")
        api_credentials = config_loader.get_api_credentials()
        
        # データベース初期化
        db_manager = DatabaseManager()
        
        # 通知マネージャー初期化
        notification_manager = NotificationManager(
            telegram_config=notifications_config["telegram"],
            discord_config=notifications_config["discord"],
            db_manager=db_manager
        )
        
        # アラートエンジン初期化
        alert_engine = AlertEngine(
            alerts_config=alerts_config["alerts"],
            db_manager=db_manager,
            notification_manager=notification_manager
        )
        
        # Polymarket クライアント初期化
        poly_client = PolymarketClient(
            api_key=api_credentials["POLYMARKET_API_KEY"],
            api_secret=api_credentials["POLYMARKET_API_SECRET"],
            api_passphrase=api_credentials["POLYMARKET_API_PASSPHRASE"],
            private_key=api_credentials["POLYMARKET_PRIVATE_KEY"],
            funder_address=api_credentials["POLYMARKET_FUNDER_ADDRESS"]
        )
        
        # 価格モニター初期化（Week 2版）
        async def on_price_update(data: dict):
            """価格更新時のコールバック（拡張版）"""
            market_id = data.get("market_id")
            price = data.get("price")
            volume = data.get("volume")
            market_name = data.get("market_name", "Unknown")
            
            if market_id and price is not None:
                # DBに保存
                db_manager.save_price(market_id, market_name, price, volume)
                
                # アラートチェック
                await alert_engine.check_alerts(market_id, market_name, price, volume)
                
                logger.info(f"価格更新: {market_name} = {price}")
        
        # WebSocket接続
        ws_url = config["polymarket"]["websocket"]
        ws_client = WebSocketClient(
            ws_url=ws_url,
            on_message=on_price_update,
            reconnect_delay=config["monitoring"]["reconnect_delay_seconds"],
            max_reconnect_attempts=config["monitoring"]["max_reconnect_attempts"]
        )
        
        await ws_client.connect()
        
        # マーケット購読
        enabled_markets = [m for m in markets_config["markets"] if m.get("enabled", True)]
        for market in enabled_markets:
            await ws_client.subscribe_to_market(market["market_id"])
        
        logger.info(f"監視開始: {len(enabled_markets)} マーケット, {len(alerts_config['alerts'])} アラート")
        
        # メッセージ受信ループ
        await ws_client.listen()
        
    except KeyboardInterrupt:
        logger.info("プログラムを終了します...")
    except Exception as e:
        logger.error(f"エラーが発生しました: {e}", exc_info=True)
    finally:
        if 'ws_client' in locals():
            await ws_client.close()
        logger.info("=== PolyBot Framework 終了 ===")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🧪 テスト手順

### 1. Telegram Bot 設定

```bash
# BotFatherで新しいBotを作成
# https://t.me/BotFather

# .envに追加
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 2. Discord Webhook 設定（オプション）

```bash
# Discord Server Settings → Integrations → Webhooks

# .envに追加
DISCORD_WEBHOOK_URL=your_webhook_url_here
```

### 3. 動作確認

```bash
# コンテナ再起動
docker-compose down
docker-compose up --build

# アラート設定を調整して通知テスト
# config/alerts.yaml の threshold を現在価格付近に設定
```

---

## ✅ Week 2 完了条件

1. ✅ 価格データがSQLiteに保存される
2. ✅ アラート条件が正しく判定される
3. ✅ Telegram通知が届く
4. ✅ Discord通知が届く（有効化時）
5. ✅ クールダウン機能が動作する
6. ✅ 通知履歴がDBに記録される

---

**Week 2完了で、実用的な価格監視ツールが完成します！** 🎉