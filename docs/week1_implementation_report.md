# PolyBot Framework - Week 1 実装レポート

## 実施日: 2026-02-14

---

## 1. 実装内容

### プロジェクト構成

```
polybot/
├── docker-compose.yml          # Docker Compose設定
├── Dockerfile                  # Pythonコンテナ定義
├── requirements.txt            # Python依存パッケージ
├── .env.example                # 環境変数テンプレート
├── .gitignore
├── config/
│   ├── config.yaml             # API・監視設定
│   └── markets.yaml            # 監視マーケット設定
├── src/
│   ├── main.py                 # エントリーポイント
│   ├── api/
│   │   ├── polymarket_client.py  # Polymarket REST APIクライアント
│   │   └── websocket_client.py   # WebSocket接続管理
│   ├── monitor/
│   │   └── price_monitor.py      # 価格監視・イベント処理
│   └── utils/
│       ├── logger.py             # Loguruログ設定
│       └── config_loader.py      # YAML/環境変数読み込み
├── data/
│   └── .gitkeep
├── logs/
│   └── .gitkeep
└── docs/
    └── week1_implementation_report.md
```

### 使用ライブラリ

| パッケージ | バージョン | 用途 |
|-----------|-----------|------|
| py-clob-client | >=0.34.0 | Polymarket公式SDK（CLOB API） |
| aiohttp | 3.9.1 | Gamma API非同期HTTPクライアント |
| websockets | 12.0 | WebSocket接続 |
| loguru | 0.7.2 | ログ管理 |
| PyYAML | 6.0.1 | 設定ファイル読み込み |
| python-dotenv | 1.0.0 | .env環境変数読み込み |

### 実装した機能

1. **Docker環境構築**
   - `python:3.11-slim` ベースイメージ
   - `PYTHONDONTWRITEBYTECODE=1` で .pyc キャッシュ無効化
   - 起動時に `__pycache__` を自動削除
   - src/config/data/logs をボリュームマウント（開発時ホットリロード対応）

2. **Polymarket REST APIクライアント (`polymarket_client.py`)**
   - CLOB API接続確認 (`get_ok`)
   - サーバー時刻取得 (`get_server_time`)
   - ミッドポイント価格取得 (`get_midpoint`)
   - オーダーブック取得 (`get_order_book`)
   - 最終取引価格取得 (`get_last_trade_price`)
   - Gamma APIマーケット一覧取得 (`get_markets_from_gamma`)
   - Gamma APIマーケット個別取得 (`get_market_by_condition_id`)

3. **WebSocketクライアント (`websocket_client.py`)**
   - `wss://ws-subscriptions-clob.polymarket.com/ws/market` への接続
   - マーケット購読/解除（`assets_ids` 形式）
   - 10秒間隔のPING keep-alive
   - 自動再接続（最大10回、5秒間隔）
   - 再接続時の自動再購読

4. **価格監視 (`price_monitor.py`)**
   - `book` イベント: オーダーブックスナップショット（bids/asks）
   - `price_changes` イベント: リアルタイム価格更新（price, size, side, best_bid, best_ask）
   - `last_trade_price` イベント: 最終取引価格
   - `tick_size_change` イベント: ティックサイズ変更

5. **マーケット自動検出 (`main.py`)**
   - `auto_discover: true` 設定でGamma APIからアクティブマーケットを自動取得
   - 解決済みマーケット（prices=[1,0]）の自動スキップ
   - 手動指定モード（conditionId直接指定）にも対応

---

## 2. 設計書からの変更点

| 設計書の内容 | 実際の実装 | 理由 |
|-------------|-----------|------|
| `polymarket-apis` パッケージ | `py-clob-client>=0.34.0` | 設計書のパッケージは非公式。公式SDKに変更 |
| Gamma APIをSDK経由で取得 | `aiohttp` で直接REST呼び出し | 公式SDKにGamma APIは含まれない |
| WebSocket購読形式: `{type: "subscribe", channel: "market"}` | `{assets_ids: [...], type: "market"}` | 実際のPolymarket WebSocket仕様に準拠 |
| WebSocket応答: `{event_type: "price_change", ...}` (単一dict) | `{market: "...", price_changes: [...]}` (ラッパー形式) | 実際のWebSocket応答形式に準拠 |
| オーダーブックフィールド: `buys`/`sells` | `bids`/`asks` | 実際のAPI応答フィールド名に準拠 |
| 固定マーケットID指定のみ | `auto_discover` モード追加 | ダミーIDでは解決済みマーケットしか返らない問題を解決 |
| `docker-compose.yml` に `version: '3.8'` | `version` 削除 | Docker Compose V2で非推奨警告が出るため |

---

## 3. 開発中に遭遇したバグと修正

### Bug 1: clobTokenIds のパースエラー
- **症状**: トークンIDに `["` や `"]` が含まれ、APIが404を返す
- **原因**: Gamma APIの `clobTokenIds` はJSON文字列（`'["token1","token2"]'`）だが、カンマ分割していた
- **修正**: `json.loads()` でパースするように変更

### Bug 2: WebSocketメッセージがリスト形式
- **症状**: `'list' object has no attribute 'get'`
- **原因**: WebSocketの `book` イベントはリスト `[{...}, {...}]` で届くが、dict前提で処理していた
- **修正**: `on_price_update` でリスト/dict両方を判定し、リストの場合は各要素を個別処理

### Bug 3: 解決済みマーケットの監視
- **症状**: オーダーブックが存在せず404エラー、WebSocketで更新が来ない
- **原因**: `markets.yaml` のダミーID `0x1234567890abcdef` が解決済みマーケットにマッチ
- **修正**: `auto_discover` モードを追加し、Gamma APIからアクティブマーケットを自動取得。`is_market_active()` で解決済みマーケットをスキップ

### Bug 4: `__pycache__` による古いコードの実行
- **症状**: ソースコード修正後も古いエラーメッセージが出続ける
- **原因**: Dockerビルド時に生成された `.pyc` キャッシュがボリュームマウント後も残存
- **修正**: `PYTHONDONTWRITEBYTECODE=1` 環境変数と、起動時の `__pycache__` 削除コマンドを追加

### Bug 5: `asset_id` が None の場合のクラッシュ
- **症状**: `'NoneType' object is not subscriptable`
- **原因**: 一部のイベントで `asset_id` が欠落しており、`asset_id[:16]` でクラッシュ
- **修正**: 各ハンドラーに `if not asset_id: return` ガードを追加

### Bug 6: オーダーブックフィールド名の不一致
- **症状**: `[BOOK]` で常に `bids=0 | asks=0`
- **原因**: コードは `buys`/`sells` を参照していたが、実際のAPIは `bids`/`asks`
- **修正**: `data.get("bids")` / `data.get("asks")` に変更

### Bug 7: price_change イベントのラッパー形式
- **症状**: 価格更新が一切ログに出ない
- **原因**: 実際のWebSocketデータは `{market: "...", price_changes: [...]}` 形式で `event_type` フィールドが無い
- **修正**: `_process_event` で `"price_changes" in data` を判定し、内部配列をイテレート

---

## 4. 動作確認結果

```
=== PolyBot Framework 起動 ===
設定ファイル読み込み完了
Polymarket クライアント初期化完了
CLOB API接続確認: OK
サーバー時刻: 1771039054
Gamma APIからアクティブなマーケットを自動取得中 (上限: 3件)...
Gamma API: 9件のマーケット取得
監視対象: Will Trump deport less than 250,000? | outcomes: ["Yes", "No"] | prices: ["0.0475", "0.9525"]
  ミッドポイント: 1016769973636871... = 0.0465
  ミッドポイント: 4153292802911610... = 0.9535
合計 3 マーケット / 6 トークンを監視
WebSocket接続成功: wss://ws-subscriptions-clob.polymarket.com/ws/market
マーケット購読開始: [...]
価格監視開始...
[BOOK] asset=1016769973636871... | best_bid=0.001 | best_ask=0.999 | bids=15 | asks=54
[BOOK] asset=4153292802911610... | best_bid=0.001 | best_ask=0.999 | bids=54 | asks=15
[PRICE] asset=3044278079904807... | side=BUY | price=0.051 | size=496.43 | bid=0.131 | ask=0.135
[PRICE] asset=1324468108632108... | side=SELL | price=0.949 | size=137.43 | bid=0.865 | ask=0.869
```

### Week 1 完了チェックリスト

- [x] Dockerコンテナが安定稼働
- [x] Polymarket REST APIでマーケット情報取得成功
- [x] WebSocketで価格データのリアルタイム受信
- [x] ログに価格更新が継続的に出力される
- [x] エラーハンドリングが機能（再接続、Noneガード等）

---

## 5. 起動方法

```bash
# 1. 環境変数設定
cp .env.example .env
# .env を編集してAPI認証情報を入力

# 2. ビルド & 起動
docker-compose up --build

# 3. バックグラウンド起動
docker-compose up -d --build

# 4. ログ確認
docker-compose logs -f
```

---

## 6. 次のステップ（Week 2 に向けて）

- 取引ロジック（シグナル検出）の実装
- CLOB認証クライアントの初期化（注文発行用）
- 価格データのDB/CSV保存
- バックテスト用データ収集
