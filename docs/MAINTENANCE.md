# PolyBot 保守ガイド

本ドキュメントは PolyBot の運用・保守を担当するエンジニア向けのリファレンスです。

---

## 1. システム構成

### サービス一覧

| サービス名 | コンテナ名 | 役割 | ポート |
|------------|-----------|------|--------|
| `polybot` | polybot-framework | Bot 本体（価格監視・自動売買） | なし |
| `web` | polybot-web | Web API + ダッシュボード配信 | 8000 |

両サービスは `polybot-network`（bridge）で接続され、SQLite（`data/polybot.db`）を共有しています。

### Docker ボリュームマウント

```
ホスト        →  コンテナ
./config      →  /app/config     # 設定ファイル（YAML + strategy.py）
./data        →  /app/data       # SQLite DB + JSONL 価格データ
./logs        →  /app/logs       # Loguru ログファイル
./src         →  /app/src        # ソースコード（--reload で反映）
./reports     →  /app/reports    # バックテストレポート（web のみ）
```

### Dockerfile（マルチステージビルド）

```
Stage 1: node:18-alpine
  └─ src/web/frontend/ をビルド → /app/frontend/dist

Stage 2: python:3.11-slim
  └─ requirements.txt インストール
  └─ ソースコード COPY
  └─ Stage 1 の dist/ を src/web/frontend/dist にコピー
```

---

## 2. 起動・停止・再起動

```bash
# 起動（初回 or Dockerfile 変更時は --build を付ける）
docker-compose up --build -d

# ログ確認
docker-compose logs -f web
docker-compose logs -f polybot

# 停止
docker-compose down

# 再起動（設定変更後）
docker-compose restart web
docker-compose restart polybot

# 完全リビルド（依存パッケージ変更時）
docker-compose down && docker-compose up --build -d
```

---

## 3. ディレクトリ構成と責務

### バックエンド（`src/`）

```
src/
├── main.py                  # Bot エントリーポイント（asyncio.run）
├── api/
│   ├── polymarket_client.py # REST API クライアント（CLOB + Gamma）
│   └── websocket_client.py  # WebSocket 接続管理・自動再接続
├── alerts/
│   ├── alert_engine.py      # alerts.yaml のルール評価
│   ├── alert_handler.py     # PriceMonitor から呼ばれるハンドラー
│   └── conditions.py        # アラート条件の評価ロジック
├── backtester/
│   ├── backtest_engine.py   # シミュレーションコア（P&L 計算）
│   ├── data_fetcher.py      # JSONL / DB からの過去データ取得
│   └── performance_analyzer.py  # メトリクス計算・グラフ生成
├── database/
│   ├── db_manager.py        # CRUD 操作（Session 管理）
│   └── models.py            # SQLAlchemy テーブル定義
├── executor/
│   ├── order_executor.py    # 注文実行（スリッページ計算含む）
│   └── position_manager.py  # ポジション更新・P&L 計算
├── monitor/
│   ├── price_monitor.py     # 価格イベントハブ（ハンドラー登録）
│   └── data_recorder.py     # JSONL ファイルへの価格記録
├── notifications/
│   ├── notification_manager.py  # 通知ルーティング
│   ├── telegram_bot.py      # Telegram Bot API
│   └── discord_bot.py       # Discord Webhook
├── risk/
│   └── risk_manager.py      # リスクチェック・サーキットブレーカー
├── strategy/
│   └── strategy_handler.py  # calculate_signal の呼び出し・結果処理
├── utils/
│   ├── config_loader.py     # YAML / .env ロード
│   └── logger.py            # Loguru 設定
└── web/
    ├── api.py               # FastAPI アプリケーション
    └── frontend/            # React SPA
```

### フロントエンド（`src/web/frontend/src/`）

```
src/
├── main.tsx                 # ReactDOM + プロバイダー（Chakra/Query/Router）
├── App.tsx                  # ルーティング定義
├── theme.ts                 # Chakra UI ダークテーマ
├── api/
│   ├── client.ts            # fetch ラッパー（apiFetch<T>）
│   └── endpoints.ts         # 各 API 呼び出し関数
├── types/
│   └── api.ts               # API レスポンスの TypeScript 型定義
├── hooks/
│   ├── useStatus.ts         # GET /api/status（5 秒ポーリング）
│   ├── usePositions.ts      # GET /api/positions（10 秒）
│   ├── useTrades.ts         # GET /api/trades（30 秒）
│   ├── usePerformance.ts    # GET /api/performance（30 秒）
│   ├── useLogs.ts           # GET /api/logs（2 秒）
│   └── useBacktest.ts       # POST /api/backtest（useMutation）
├── store/
│   └── uiStore.ts           # Zustand: pollingEnabled, sidebarOpen
├── components/
│   ├── Layout.tsx           # サイドバー + Outlet（レスポンシブ）
│   ├── Sidebar.tsx          # ナビゲーション + ポーリングスイッチ
│   ├── StatCard.tsx         # メトリクス表示カード
│   └── StatusBadge.tsx      # Running/Stopped バッジ
└── features/
    ├── dashboard/
    │   ├── DashboardPage.tsx     # ダッシュボード統合ページ
    │   ├── StatusPanel.tsx       # Bot 状態・資産・PnL
    │   ├── PositionsTable.tsx    # ポジション一覧テーブル
    │   ├── PerformancePanel.tsx  # 勝率・損益メトリクス
    │   └── LogPanel.tsx          # ログ表示（自動スクロール）
    └── backtest/
        ├── BacktestPage.tsx      # バックテスト統合ページ
        ├── BacktestForm.tsx      # パラメータ入力フォーム
        └── BacktestResults.tsx   # 結果表示・Equity Curve グラフ
```

---

## 4. データベース

### 接続先

- ファイル: `data/polybot.db`（SQLite）
- ORM: SQLAlchemy 2.0
- モデル定義: `src/database/models.py`

### テーブル一覧

| テーブル | 用途 |
|----------|------|
| `positions` | アクティブポジション（asset_id, side, size_usdc, average_price） |
| `trades` | 取引履歴（action, price, amount_usdc, realized_pnl） |
| `price_history` | 価格記録（market, price, best_bid, best_ask, timestamp） |
| `alert_logs` | アラート発火履歴 |
| `notification_history` | 通知送信履歴 |

### DB の直接確認

```bash
# コンテナ内で
docker exec -it polybot-web python -c "
import sqlite3
conn = sqlite3.connect('data/polybot.db')
for row in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"'):
    print(row[0])
conn.close()
"

# ポジション確認
docker exec -it polybot-web python -c "
import sqlite3
conn = sqlite3.connect('data/polybot.db')
for row in conn.execute('SELECT * FROM positions WHERE size_usdc > 0'):
    print(row)
conn.close()
"
```

### DB の初期化（リセット）

```bash
# Bot を停止してからリセット
docker-compose down
rm data/polybot.db
docker-compose up -d
```

---

## 5. ログ

### 形式

```
{YYYY-MM-DD HH:mm:ss} | {LEVEL}    | {module}:{function} - {message}
```

例:
```
2026-02-15 10:00:00 | INFO     | web.api:startup_event - Web API 起動完了
2026-02-15 10:00:01 | WARNING  | monitor:check - 価格急変検出
```

### ファイル

- 場所: `logs/polybot_YYYY-MM-DD.log`
- ローテーション: 500 MB ごとに自動分割
- 保持期間: 10 日間（自動削除）
- Web API（`GET /api/logs`）からも取得可能

### ログレベルの変更

`.env` の `LOG_LEVEL` を変更して再起動:

```bash
# .env
LOG_LEVEL=DEBUG    # DEBUG / INFO / WARNING / ERROR / CRITICAL
```

---

## 6. API エンドポイント詳細

### GET /api/status

```json
{
  "status": "running",
  "version": "1.0.0",
  "daily_pnl": 12.345678,
  "total_assets_usdc": 500.0
}
```

### GET /api/positions

```json
{
  "positions": [
    {
      "asset_id": "0x...",
      "market": "0x...",
      "side": "BUY",
      "size_usdc": 100.0,
      "average_price": 0.45,
      "realized_pnl": 5.0,
      "opened_at": "2026-02-15T10:00:00",
      "updated_at": "2026-02-15T12:00:00"
    }
  ],
  "total_value_usdc": 100.0
}
```

### GET /api/trades

パラメータ: `limit`（1-1000, default=100）, `since_hours`（1-720, default=24）

### GET /api/performance

パラメータ: `days`（1-365, default=7）

```json
{
  "total_pnl": 42.5,
  "win_rate": 65.0,
  "total_trades": 20,
  "winning_trades": 13,
  "losing_trades": 7,
  "period_days": 7
}
```

### GET /api/logs

パラメータ: `limit`（1-1000, default=100）, `level`（optional: INFO/WARNING/ERROR）

### POST /api/backtest

パラメータ: `days`（1-90）, `market_id`（optional）, `initial_capital`（min=100）

レスポンスに `analysis`、`equity_curve`、`trades` を含む。

---

## 7. フロントエンド開発

### 開発サーバー

```bash
cd src/web/frontend
npm install
npm run dev       # http://localhost:5173
```

Vite の設定（`vite.config.ts`）で `/api` へのリクエストは `localhost:8000` にプロキシされます。

### ビルド

```bash
cd src/web/frontend
npm run build     # dist/ に出力
```

ビルド成果物は FastAPI が自動検出して配信します（`api.py` 末尾の静的ファイルマウント）。

### 状態管理の設計方針

| 種類 | ツール | 用途 |
|------|--------|------|
| サーバー状態 | TanStack Query | API データ取得・キャッシュ・ポーリング |
| UI 状態 | Zustand | ポーリングON/OFF・サイドバー開閉 |

TanStack Query のポーリング間隔は各フック内で定義されており、Zustand の `pollingEnabled` フラグで一括 ON/OFF できます。

### 新しい API エンドポイントの追加手順

1. `src/web/api.py` にルート追加
2. `src/web/frontend/src/types/api.ts` にレスポンス型追加
3. `src/web/frontend/src/api/endpoints.ts` に呼び出し関数追加
4. `src/web/frontend/src/hooks/` にカスタムフック追加
5. `features/` 配下にコンポーネント作成
6. `tests/test_web_api.py` にテスト追加

---

## 8. テスト

### 実行

```bash
python -m pytest tests/test_web_api.py -v
```

### テスト構成

| クラス | 対象 |
|--------|------|
| `TestStatusEndpoint` | `/api/status`（基本・daily_pnl・mock DB） |
| `TestPositionsEndpoint` | `/api/positions`（空・データあり） |
| `TestTradesEndpoint` | `/api/trades`（空・パラメータ指定） |
| `TestPerformanceEndpoint` | `/api/performance`（空・日数指定） |
| `TestBacktestEndpoint` | `/api/backtest`（データなし・モックデータ） |
| `TestLogsEndpoint` | `/api/logs`（ディレクトリなし・パース・フィルタ・件数制限） |
| `TestLoadCalculateSignal` | 戦略ファイルの動的ロード |

テストパターン: `FastAPI TestClient` + `unittest.mock.MagicMock` で DB をモック。

---

## 9. トラブルシューティング

### Bot が起動しない

```bash
docker-compose logs polybot
```

よくある原因:
- `.env` の API キーが未設定 → `.env.example` を参照
- `config/strategy.py` に構文エラー → Python で直接実行して確認
- ネットワークエラー → Polymarket API の疎通確認

### Web ダッシュボードが表示されない

```bash
docker-compose logs web
```

よくある原因:
- フロントエンドがビルドされていない → `docker-compose up --build` を実行
- ポート 8000 が他プロセスに使用されている → `lsof -i :8000` で確認
- `src/web/frontend/dist/` が存在しない → ログに "Frontend build not found" と出力される

### API レスポンスが空

- DB ファイルが存在しない → `data/` ディレクトリの確認
- Bot が起動していない → `polybot` コンテナの状態確認
- `_db_manager` が `None` → `startup_event` のログ確認

### ポーリングが動かない

- ダッシュボードのサイドバーで "Polling" スイッチが ON になっているか確認
- ブラウザの DevTools > Network タブで API リクエストを確認
- CORS エラーの場合は `api.py` の `allow_origins` を確認

---

## 10. 設定変更チェックリスト

| 変更内容 | 必要な操作 |
|----------|-----------|
| `config/*.yaml` の変更 | `docker-compose restart polybot web` |
| `config/strategy.py` の変更 | `docker-compose restart polybot`（Web は不要） |
| `.env` の変更 | `docker-compose down && docker-compose up -d` |
| `requirements.txt` の変更 | `docker-compose up --build` |
| フロントエンドのコード変更 | `docker-compose up --build`（再ビルド必要） |
| `src/web/api.py` の変更 | 自動反映（`--reload` 有効） |

---

## 11. バックアップ

### 定期バックアップ対象

| ファイル/ディレクトリ | 重要度 | 内容 |
|---------------------|--------|------|
| `.env` | 必須 | API キー・シークレット |
| `config/` | 必須 | 全設定ファイル |
| `data/polybot.db` | 推奨 | 取引履歴・ポジション・価格データ |
| `data/*.jsonl` | 任意 | 生の価格ログ（バックテスト用） |

### バックアップスクリプト例

```bash
BACKUP_DIR="backup/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR"
cp .env "$BACKUP_DIR/"
cp -r config/ "$BACKUP_DIR/"
cp data/polybot.db "$BACKUP_DIR/"
```
