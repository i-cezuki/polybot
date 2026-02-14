# PolyBot Framework - Week 1 実装設計書

## 📋 Week 1 の目標

**Polymarket API統合と基本的な価格取得機能の実装**

### 成果物
- Dockerコンテナ環境の構築
- Polymarket APIとの接続確認
- WebSocketでリアルタイム価格取得
- 基本的なログ出力

---

## 🏗️ プロジェクト構成

```
polybot-framework/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── config/
│   ├── config.yaml          # 基本設定（API認証情報）
│   └── markets.yaml         # 監視対象マーケットリスト
├── src/
│   ├── __init__.py
│   ├── main.py              # エントリーポイント
│   ├── api/
│   │   ├── __init__.py
│   │   ├── polymarket_client.py   # Polymarket API クライアント
│   │   └── websocket_client.py    # WebSocket 接続管理
│   ├── monitor/
│   │   ├── __init__.py
│   │   └── price_monitor.py       # 価格監視ロジック
│   └── utils/
│       ├── __init__.py
│       ├── logger.py              # ログ設定
│       └── config_loader.py       # 設定ファイル読み込み
├── data/
│   └── .gitkeep
└── logs/
    └── .gitkeep
```

---

## 🐳 Docker環境設定

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# システム依存パッケージ
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python依存パッケージ
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコード
COPY . .

CMD ["python", "src/main.py"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  polybot:
    build: .
    container_name: polybot-framework
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./logs:/app/logs
      - ./src:/app/src  # 開発時はコードをマウント
    env_file:
      - .env
    restart: unless-stopped
    networks:
      - polybot-network

networks:
  polybot-network:
    driver: bridge
```

### requirements.txt

```txt
# Polymarket SDK
polymarket-apis==0.1.0

# WebSocket
websockets==12.0

# 設定ファイル
PyYAML==6.0.1
python-dotenv==1.0.0

# ログ
loguru==0.7.2

# 非同期処理
aiohttp==3.9.1
asyncio==3.4.3

# ユーティリティ
python-dateutil==2.8.2
```

### .env.example

```bash
# Polymarket API認証情報
POLYMARKET_API_KEY=your_api_key_here
POLYMARKET_API_SECRET=your_api_secret_here
POLYMARKET_API_PASSPHRASE=your_passphrase_here

# ウォレット情報
POLYMARKET_PRIVATE_KEY=your_private_key_here
POLYMARKET_FUNDER_ADDRESS=your_funder_address_here

# ログレベル
LOG_LEVEL=INFO

# 環境（development / production）
ENVIRONMENT=development
```

---

## 📝 設定ファイル

### config/config.yaml

```yaml
# Polymarket API設定
polymarket:
  api:
    endpoint: "https://clob.polymarket.com"
    websocket: "wss://ws-subscriptions-clob.polymarket.com/ws"
  
  # レート制限（Polymarket公式制限）
  rate_limits:
    rest_api: 100  # リクエスト/分
    trading_api: 60  # 注文/分

# ログ設定
logging:
  level: INFO
  format: "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>"
  rotation: "500 MB"
  retention: "10 days"
  
# 監視設定
monitoring:
  interval_seconds: 1  # 価格監視間隔
  reconnect_delay_seconds: 5  # WebSocket再接続待機時間
  max_reconnect_attempts: 10
```

### config/markets.yaml

```yaml
# 監視対象マーケットリスト
markets:
  - market_id: "0x1234567890abcdef"  # 実際のMarket ID（conditionId）
    name: "気象予測テスト市場"
    description: "2026年2月の東京の降水確率"
    enabled: true
    
  # 追加マーケット例（コメントアウト）
  # - market_id: "0xabcdef1234567890"
  #   name: "ビットコイン価格予測"
  #   description: "BTC $100k by end of 2026?"
  #   enabled: false
```

---

## 💻 コア実装

### src/utils/logger.py

```python
"""ログ設定モジュール"""
from loguru import logger
import sys
from pathlib import Path

def setup_logger(log_level: str = "INFO"):
    """
    Loguruロガーの初期設定
    
    Args:
        log_level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
    """
    # 既存のハンドラーを削除
    logger.remove()
    
    # コンソール出力
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level=log_level,
        colorize=True
    )
    
    # ファイル出力
    log_path = Path("logs")
    log_path.mkdir(exist_ok=True)
    
    logger.add(
        log_path / "polybot_{time:YYYY-MM-DD}.log",
        rotation="500 MB",
        retention="10 days",
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}"
    )
    
    return logger
```

### src/utils/config_loader.py

```python
"""設定ファイル読み込みモジュール"""
import yaml
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv
import os

class ConfigLoader:
    """設定ファイル読み込みクラス"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        load_dotenv()  # .envファイル読み込み
    
    def load_yaml(self, filename: str) -> Dict[str, Any]:
        """
        YAMLファイルを読み込む
        
        Args:
            filename: ファイル名（例: "config.yaml"）
            
        Returns:
            Dict: 設定内容
        """
        filepath = self.config_dir / filename
        
        if not filepath.exists():
            raise FileNotFoundError(f"設定ファイルが見つかりません: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def get_api_credentials(self) -> Dict[str, str]:
        """
        環境変数からAPI認証情報を取得
        
        Returns:
            Dict: API認証情報
        """
        required_keys = [
            "POLYMARKET_API_KEY",
            "POLYMARKET_API_SECRET",
            "POLYMARKET_API_PASSPHRASE",
            "POLYMARKET_PRIVATE_KEY",
            "POLYMARKET_FUNDER_ADDRESS"
        ]
        
        credentials = {}
        missing_keys = []
        
        for key in required_keys:
            value = os.getenv(key)
            if not value:
                missing_keys.append(key)
            credentials[key] = value
        
        if missing_keys:
            raise ValueError(f"必要な環境変数が設定されていません: {', '.join(missing_keys)}")
        
        return credentials
```

### src/api/polymarket_client.py

```python
"""Polymarket API クライアント"""
from typing import Dict, List, Any, Optional
from loguru import logger
import asyncio
from polymarket_apis import ClobClient, GammaClient

class PolymarketClient:
    """Polymarket API クライアントラッパー"""
    
    def __init__(self, api_key: str, api_secret: str, api_passphrase: str, 
                 private_key: str, funder_address: str):
        """
        初期化
        
        Args:
            api_key: APIキー
            api_secret: APIシークレット
            api_passphrase: APIパスフレーズ
            private_key: ウォレット秘密鍵
            funder_address: Funderアドレス
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self.private_key = private_key
        self.funder_address = funder_address
        
        # CLOBクライアント（取引用）
        self.clob_client = None
        
        # Gammaクライアント（マーケットデータ取得用）
        self.gamma_client = GammaClient()
        
        logger.info("Polymarket クライアント初期化完了")
    
    async def initialize_clob(self):
        """CLOB クライアントの初期化（認証が必要な操作用）"""
        try:
            # Week 1では読み取り専用なので、認証は後回し
            # self.clob_client = ClobClient(...)
            logger.info("CLOB クライアント初期化スキップ（Week 1は読み取り専用）")
        except Exception as e:
            logger.error(f"CLOB クライアント初期化失敗: {e}")
            raise
    
    async def get_market_info(self, condition_id: str) -> Optional[Dict[str, Any]]:
        """
        マーケット情報を取得
        
        Args:
            condition_id: マーケットID（conditionId）
            
        Returns:
            Dict: マーケット情報
        """
        try:
            # Gamma APIでマーケット情報取得
            market = self.gamma_client.get_market(condition_id)
            
            if market:
                logger.info(f"マーケット情報取得成功: {market.get('question', 'N/A')}")
                return market
            else:
                logger.warning(f"マーケットが見つかりません: {condition_id}")
                return None
                
        except Exception as e:
            logger.error(f"マーケット情報取得エラー: {e}")
            return None
    
    async def get_orderbook(self, token_id: str) -> Optional[Dict[str, Any]]:
        """
        オーダーブック（価格情報）を取得
        
        Args:
            token_id: トークンID
            
        Returns:
            Dict: オーダーブック
        """
        try:
            # 価格情報取得（REST API経由）
            # polymarket-apisのメソッドを使用
            orderbook = self.gamma_client.get_price(token_id)
            
            if orderbook:
                logger.debug(f"価格取得: token_id={token_id}, price={orderbook.get('price', 'N/A')}")
                return orderbook
            else:
                logger.warning(f"価格情報が見つかりません: {token_id}")
                return None
                
        except Exception as e:
            logger.error(f"価格取得エラー: {e}")
            return None
```

### src/api/websocket_client.py

```python
"""WebSocket クライアント"""
import asyncio
import websockets
import json
from typing import Callable, Optional
from loguru import logger

class WebSocketClient:
    """Polymarket WebSocket クライアント"""
    
    def __init__(self, ws_url: str, on_message: Callable, 
                 reconnect_delay: int = 5, max_reconnect_attempts: int = 10):
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
        
    async def connect(self):
        """WebSocket接続を確立"""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            self.is_running = True
            self.reconnect_count = 0
            logger.info(f"WebSocket接続成功: {self.ws_url}")
            
        except Exception as e:
            logger.error(f"WebSocket接続失敗: {e}")
            raise
    
    async def subscribe_to_market(self, market_id: str):
        """
        特定のマーケットを購読
        
        Args:
            market_id: マーケットID
        """
        if not self.websocket:
            logger.error("WebSocketが接続されていません")
            return
        
        subscribe_msg = {
            "type": "subscribe",
            "channel": "market",
            "market_id": market_id
        }
        
        try:
            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"マーケット購読開始: {market_id}")
        except Exception as e:
            logger.error(f"購読メッセージ送信失敗: {e}")
    
    async def listen(self):
        """メッセージ受信ループ"""
        while self.is_running:
            try:
                if not self.websocket:
                    await self._reconnect()
                    continue
                
                message = await self.websocket.recv()
                data = json.loads(message)
                
                # コールバック関数を実行
                await self.on_message(data)
                
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket接続が切断されました")
                await self._reconnect()
                
            except Exception as e:
                logger.error(f"メッセージ受信エラー: {e}")
                await asyncio.sleep(1)
    
    async def _reconnect(self):
        """WebSocket再接続"""
        if self.reconnect_count >= self.max_reconnect_attempts:
            logger.error(f"最大再接続回数（{self.max_reconnect_attempts}）に達しました")
            self.is_running = False
            return
        
        self.reconnect_count += 1
        logger.info(f"再接続試行 {self.reconnect_count}/{self.max_reconnect_attempts}")
        
        await asyncio.sleep(self.reconnect_delay)
        
        try:
            await self.connect()
        except Exception as e:
            logger.error(f"再接続失敗: {e}")
    
    async def close(self):
        """WebSocket接続を閉じる"""
        self.is_running = False
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket接続を閉じました")
```

### src/monitor/price_monitor.py

```python
"""価格監視モジュール"""
from typing import Dict, Any
from loguru import logger
from datetime import datetime

class PriceMonitor:
    """価格監視クラス"""
    
    def __init__(self):
        """初期化"""
        self.price_data = {}  # market_id -> 最新価格のマッピング
        logger.info("PriceMonitor 初期化完了")
    
    async def on_price_update(self, data: Dict[str, Any]):
        """
        価格更新時のコールバック
        
        Args:
            data: WebSocketから受信したデータ
        """
        try:
            # データ構造は実際のPolymarket WebSocket仕様に合わせて調整
            market_id = data.get("market_id")
            price = data.get("price")
            timestamp = data.get("timestamp", datetime.utcnow().isoformat())
            
            if market_id and price is not None:
                self.price_data[market_id] = {
                    "price": price,
                    "timestamp": timestamp
                }
                
                logger.info(f"価格更新: market_id={market_id}, price={price}, time={timestamp}")
            
        except Exception as e:
            logger.error(f"価格更新処理エラー: {e}")
    
    def get_current_price(self, market_id: str) -> float:
        """
        現在価格を取得
        
        Args:
            market_id: マーケットID
            
        Returns:
            float: 現在価格
        """
        if market_id in self.price_data:
            return self.price_data[market_id]["price"]
        else:
            logger.warning(f"価格データが存在しません: {market_id}")
            return None
```

### src/main.py

```python
"""メインエントリーポイント"""
import asyncio
from loguru import logger
from utils.logger import setup_logger
from utils.config_loader import ConfigLoader
from api.polymarket_client import PolymarketClient
from api.websocket_client import WebSocketClient
from monitor.price_monitor import PriceMonitor

async def main():
    """メイン処理"""
    
    # ロガー初期化
    setup_logger("INFO")
    logger.info("=== PolyBot Framework 起動 ===")
    
    try:
        # 設定読み込み
        config_loader = ConfigLoader()
        config = config_loader.load_yaml("config.yaml")
        markets_config = config_loader.load_yaml("markets.yaml")
        api_credentials = config_loader.get_api_credentials()
        
        logger.info("設定ファイル読み込み完了")
        
        # Polymarket クライアント初期化
        poly_client = PolymarketClient(
            api_key=api_credentials["POLYMARKET_API_KEY"],
            api_secret=api_credentials["POLYMARKET_API_SECRET"],
            api_passphrase=api_credentials["POLYMARKET_API_PASSPHRASE"],
            private_key=api_credentials["POLYMARKET_PRIVATE_KEY"],
            funder_address=api_credentials["POLYMARKET_FUNDER_ADDRESS"]
        )
        
        # 価格モニター初期化
        price_monitor = PriceMonitor()
        
        # 監視対象マーケット情報取得
        enabled_markets = [m for m in markets_config["markets"] if m.get("enabled", True)]
        logger.info(f"監視対象マーケット数: {len(enabled_markets)}")
        
        for market in enabled_markets:
            market_id = market["market_id"]
            market_name = market.get("name", "N/A")
            
            # マーケット情報取得（REST API）
            market_info = await poly_client.get_market_info(market_id)
            
            if market_info:
                logger.info(f"マーケット: {market_name} | 質問: {market_info.get('question', 'N/A')}")
        
        # WebSocket接続
        ws_url = config["polymarket"]["websocket"]
        ws_client = WebSocketClient(
            ws_url=ws_url,
            on_message=price_monitor.on_price_update,
            reconnect_delay=config["monitoring"]["reconnect_delay_seconds"],
            max_reconnect_attempts=config["monitoring"]["max_reconnect_attempts"]
        )
        
        await ws_client.connect()
        
        # マーケット購読
        for market in enabled_markets:
            await ws_client.subscribe_to_market(market["market_id"])
        
        logger.info("価格監視開始...")
        
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

### 1. 環境構築

```bash
# リポジトリ作成
mkdir polybot-framework
cd polybot-framework

# .envファイル作成
cp .env.example .env
# .envファイルを編集してAPI認証情報を入力

# Dockerコンテナビルド
docker-compose build

# コンテナ起動
docker-compose up
```

### 2. 動作確認項目

- [ ] Dockerコンテナが正常に起動する
- [ ] ログファイルが `logs/` ディレクトリに生成される
- [ ] Polymarket API接続が成功する
- [ ] マーケット情報が取得できる
- [ ] WebSocket接続が確立される
- [ ] リアルタイム価格が受信・ログ出力される

### 3. 期待されるログ出力

```
2026-02-13 10:00:00 | INFO     | main:main - === PolyBot Framework 起動 ===
2026-02-13 10:00:01 | INFO     | config_loader:load_yaml - 設定ファイル読み込み完了
2026-02-13 10:00:01 | INFO     | polymarket_client:__init__ - Polymarket クライアント初期化完了
2026-02-13 10:00:02 | INFO     | polymarket_client:get_market_info - マーケット情報取得成功: Will it rain in Tokyo?
2026-02-13 10:00:03 | INFO     | websocket_client:connect - WebSocket接続成功: wss://ws-subscriptions-clob.polymarket.com/ws
2026-02-13 10:00:03 | INFO     | websocket_client:subscribe_to_market - マーケット購読開始: 0x1234567890abcdef
2026-02-13 10:00:05 | INFO     | price_monitor:on_price_update - 価格更新: market_id=0x1234567890abcdef, price=0.35, time=2026-02-13T10:00:05Z
```

---

## 📌 Week 1 完了条件

✅ **以下が全て動作すれば Week 1 完了**

1. Dockerコンテナが安定稼働
2. Polymarket REST APIでマーケット情報取得成功
3. WebSocketで価格データのリアルタイム受信
4. ログに価格更新が継続的に出力される
5. エラーハンドリングが機能（再接続など）

---

## 🚨 注意事項

### API制限
- REST API: 100リクエスト/分
- Trading API: 60注文/分（Week 1では未使用）

### エラー処理
- WebSocket切断時は自動再接続
- 最大10回まで再接続試行
- 失敗時は詳細ログを出力

### セキュリティ
- `.env` ファイルは `.gitignore` に追加
- 秘密鍵は絶対にコミットしない
- 本番環境では環境変数で管理

---

## 📚 参考資料

- [Polymarket公式ドキュメント](https://docs.polymarket.com/)
- [polymarket-apis GitHub](https://github.com/Polymarket/python-sdk)
- [Polymarket CLOB API](https://docs.polymarket.com/api/clob)
- [Polymarket WebSocket](https://docs.polymarket.com/websocket)

---

**この設計書をClaude Codeに渡して実装を開始してください！** 🚀