# PolyBot Framework

Polymarket 向け自動売買フレームワーク。WebSocket でリアルタイム価格を監視し、ユーザー定義の戦略に基づいてシミュレーション取引を実行します。Web ダッシュボードからポジション・損益・ログをブラウザで確認でき、バックテスト機能で戦略の検証も可能です。

## 主な機能

- **リアルタイム価格監視** - Polymarket WebSocket API による低遅延な価格フィード
- **戦略フレームワーク** - Python 関数 1 つで自由に売買ロジックを定義
- **リスク管理** - 最大ポジション・日次損失上限・サーキットブレーカー
- **Web ダッシュボード** - React SPA（ダークモード）でステータス・ポジション・ログを一覧表示
- **バックテスト** - 過去データで戦略をシミュレーション、Equity Curve をグラフ描画
- **アラート通知** - Telegram / Discord で価格変動を即時通知
- **データ記録** - 価格データを JSONL + SQLite に自動保存

## アーキテクチャ

```
┌─────────────────────────────────────────────────────┐
│                    Docker Compose                    │
│                                                     │
│  ┌──────────────┐       ┌────────────────────────┐  │
│  │   polybot    │       │         web            │  │
│  │  (Bot本体)   │       │  FastAPI + React SPA   │  │
│  │              │       │                        │  │
│  │  WebSocket ──┤       │  :8000                 │  │
│  │  Strategy    │       │  /api/* → REST API     │  │
│  │  Executor    │       │  /*     → Dashboard    │  │
│  └──────┬───────┘       └────────┬───────────────┘  │
│         │                        │                  │
│         └────── SQLite ──────────┘                  │
│                data/polybot.db                      │
└─────────────────────────────────────────────────────┘
```

## クイックスタート

### 前提条件

- Docker & Docker Compose がインストールされていること
- Polymarket API の認証情報（[取得方法](https://docs.polymarket.com/)）

### 1. リポジトリのクローン

```bash
git clone <repository-url>
cd polybot
```

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を開き、API キーやウォレット情報を入力してください。

### 3. 起動

```bash
docker-compose up --build
```

以下のサービスが起動します:

| サービス | 説明 | URL |
|----------|------|-----|
| `polybot` | Bot 本体（価格監視 + 自動売買） | - |
| `web` | Web ダッシュボード + API | http://localhost:8000 |

### 4. ダッシュボードにアクセス

ブラウザで http://localhost:8000 を開くと、ダッシュボードが表示されます。

## プロジェクト構成

```
polybot/
├── config/                  # 設定ファイル
│   ├── config.yaml          # API エンドポイント・監視設定
│   ├── markets.yaml         # 監視対象マーケット
│   ├── strategy.py          # 売買戦略（ユーザーが編集）
│   ├── alerts.yaml          # アラートルール
│   ├── risk.yaml            # リスク管理パラメータ
│   └── notifications.yaml   # 通知チャンネル設定
├── src/
│   ├── main.py              # Bot エントリーポイント
│   ├── api/                 # Polymarket API クライアント
│   ├── alerts/              # アラートエンジン
│   ├── backtester/          # バックテストエンジン
│   ├── database/            # SQLAlchemy モデル・DB 管理
│   ├── executor/            # 注文執行・ポジション管理
│   ├── monitor/             # 価格モニター・データ記録
│   ├── notifications/       # Telegram / Discord 通知
│   ├── risk/                # リスク管理
│   ├── strategy/            # 戦略ハンドラー
│   ├── utils/               # ユーティリティ
│   └── web/
│       ├── api.py           # FastAPI REST API
│       └── frontend/        # React SPA（TypeScript）
├── tests/                   # テスト
├── data/                    # DB・価格データ（自動生成）
├── logs/                    # ログファイル（自動生成）
├── reports/                 # バックテストレポート（自動生成）
├── docker-compose.yml
├── Dockerfile               # マルチステージビルド（Node.js + Python）
└── requirements.txt
```

## 戦略の書き方

`config/strategy.py` に `calculate_signal(data)` 関数を定義します。

```python
def calculate_signal(data):
    price = data["price"]
    position = data["position_usdc"]

    if price < 0.30 and position == 0:
        return {"action": "BUY", "amount": 50, "reason": "割安"}

    if price > 0.70 and position > 0:
        return {"action": "SELL", "amount": position, "reason": "利確"}

    return {"action": "HOLD", "amount": 0, "reason": "様子見"}
```

`data` に含まれるフィールド:

| キー | 型 | 説明 |
|------|----|------|
| `price` | float | 現在価格 |
| `market_id` | str | マーケット ID |
| `history` | list[dict] | 直近の価格履歴（最大 100 件） |
| `position_usdc` | float | 現在のポジション（USDC） |
| `side` | str \| None | ポジションの方向（BUY/None） |
| `best_bid` | float \| None | 最良買い気配 |
| `best_ask` | float \| None | 最良売り気配 |
| `timestamp` | str | タイムスタンプ |

詳しくは [AI_CO_PILOT_GUIDE.md](docs/AI_CO_PILOT_GUIDE.md) を参照してください。

## API エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/status` | Bot ステータス・日次損益・資産合計 |
| GET | `/api/positions` | アクティブポジション一覧 |
| GET | `/api/trades?limit=100&since_hours=24` | 取引履歴 |
| GET | `/api/performance?days=7` | パフォーマンスサマリー |
| GET | `/api/logs?limit=100&level=ERROR` | ログ取得 |
| POST | `/api/backtest?days=7&initial_capital=10000` | バックテスト実行 |

## 開発

### ローカル開発（Python + Vite）

```bash
# バックエンド
pip install -r requirements.txt
cd src && uvicorn web.api:app --reload --port 8000

# フロントエンド（別ターミナル）
cd src/web/frontend
npm install
npm run dev    # http://localhost:5173（APIは:8000にプロキシ）
```

### テスト

```bash
python -m pytest tests/test_web_api.py -v
```

### フロントエンドビルド

```bash
cd src/web/frontend
npm run build   # dist/ に出力 → FastAPI が自動配信
```

## 設定ファイル

| ファイル | 説明 |
|----------|------|
| `.env` | API キー・シークレット（Git 管理外） |
| `config/config.yaml` | API エンドポイント・レートリミット・監視間隔 |
| `config/markets.yaml` | 監視マーケット（自動検出 or 手動指定） |
| `config/strategy.py` | 売買戦略ロジック |
| `config/risk.yaml` | リスク管理（最大ポジション・損失上限・スリッページ） |
| `config/alerts.yaml` | アラート条件（価格急変・ボリューム） |
| `config/notifications.yaml` | 通知先（Telegram / Discord） |

## 技術スタック

**バックエンド:** Python 3.11 / FastAPI / SQLAlchemy / Loguru / asyncio

**フロントエンド:** React 18 / TypeScript / Vite / Chakra UI / Recharts / TanStack Query / Zustand

**インフラ:** Docker Compose / SQLite / マルチステージビルド

## ライセンス

Private
