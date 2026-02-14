# PolyBot Framework - Week 2 実装レポート

## 実施日: 2026-02-14

---

## 1. 実装内容

### プロジェクト構成（Week 2 追加分）

```
polybot/
├── config/
│   ├── config.yaml              # 既存
│   ├── markets.yaml             # 既存
│   ├── alerts.yaml              # NEW: アラートルール設定
│   └── notifications.yaml       # NEW: 通知チャンネル設定
├── src/
│   ├── main.py                  # 修正: DB・アラート・通知の統合
│   ├── database/
│   │   ├── __init__.py          # NEW
│   │   ├── models.py            # NEW: SQLAlchemy 2.x モデル
│   │   └── db_manager.py        # NEW: DB操作管理
│   ├── alerts/
│   │   ├── __init__.py          # NEW
│   │   ├── conditions.py        # NEW: 条件判定ロジック
│   │   ├── alert_engine.py      # NEW: アラート評価エンジン
│   │   └── alert_handler.py     # NEW: PriceMonitor用ハンドラー
│   └── notifications/
│       ├── __init__.py          # NEW
│       ├── telegram_bot.py      # NEW: Telegram通知
│       ├── discord_bot.py       # NEW: Discord通知
│       └── notification_manager.py  # NEW: 通知統合管理
├── tests/
│   ├── test_conditions.py       # NEW: 条件チェッカーテスト（11件）
│   ├── test_alert_engine.py     # NEW: アラートエンジンテスト（7件）
│   └── test_db_manager.py       # NEW: DB管理テスト（9件）
└── data/
    └── polybot.db               # NEW: SQLiteデータベース（実行時生成）
```

### 追加ライブラリ

| パッケージ | バージョン | 用途 |
|-----------|-----------|------|
| python-telegram-bot | 22.6 | Telegram Bot API |
| discord-webhook | 1.3.0 | Discord Webhook通知 |
| sqlalchemy | 2.0.23 | ORM / SQLiteデータベース |

### 実装した機能

1. **SQLiteデータベース (`database/`)**
   - SQLAlchemy 2.x の `DeclarativeBase` + `Mapped` 型アノテーション
   - 3テーブル: `price_history`, `alert_log`, `notification_history`
   - `DatabaseManager` クラスで CRUD 操作を提供
   - contextmanager によるセッション管理（自動 commit/rollback）
   - デフォルトパス `data/polybot.db`、起動時に自動テーブル作成

2. **アラート条件チェッカー (`alerts/conditions.py`)**
   - `check_price_below(current_price, threshold)` — 価格下限
   - `check_price_above(current_price, threshold)` — 価格上限
   - `check_price_change_percent(market, current_price, timeframe_minutes, threshold_percent)` — 変動率（DB履歴比較）
   - `check_volume_above(current_volume, threshold)` — 出来高

3. **アラートエンジン (`alerts/alert_engine.py`)**
   - `alerts.yaml` のルール定義に基づきイベント評価
   - `market_id: "*"` で全マーケット対象（ワイルドカード）
   - `match_mode: "match_any"` (OR) / `"match_all"` (AND) 対応
   - クールダウン機能: `cooldown_minutes` で同一アラートの再送抑制
   - 条件成立時に DB 保存 + 通知送信

4. **アラートハンドラー (`alerts/alert_handler.py`)**
   - PriceMonitor の `add_handler` に登録する関数
   - `price_change` イベントのみ処理
   - 受信データを DB に保存し、アラートエンジンで評価
   - 文字列→float 安全変換、タイムスタンプパース（ISO/Unix対応）

5. **Telegram通知 (`notifications/telegram_bot.py`)**
   - `python-telegram-bot` の `Bot` クラスを使用
   - 環境変数 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` 未設定時は初期化スキップ
   - 遅延インポートで未使用時のモジュール読み込みを回避

6. **Discord通知 (`notifications/discord_bot.py`)**
   - `discord-webhook` の `DiscordWebhook` を使用
   - 環境変数 `DISCORD_WEBHOOK_URL` 未設定時は初期化スキップ
   - 同期ライブラリを async ハンドラー内で呼び出し

7. **通知マネージャー (`notifications/notification_manager.py`)**
   - Telegram/Discord を統合管理
   - 各チャンネルの送信結果を `notification_history` テーブルに保存
   - 全チャンネル無効時もクラッシュしない

8. **main.py 統合**
   - 既存の `add_handler` パターンを維持（Observer パターン）
   - DataRecorder（JSONL蓄積）と AlertHandler（DB保存+アラート）が並行稼働
   - 初期化順序: DB → NotificationManager → AlertEngine → AlertHandler

---

## 2. 設計書からの変更点

| 設計書の内容 | 実際の実装 | 理由 |
|-------------|-----------|------|
| `python-telegram-bot==20.7` | `python-telegram-bot==22.6` | 20.7 は `httpx~=0.25.2` に依存し、他パッケージと競合するため最新安定版に変更 |
| `alembic==1.13.0`, `pandas==2.1.4` を含む | 除外 | Week 2 スコープ外。マイグレーションは手動 `create_all` で対応 |
| `declarative_base()` (SQLAlchemy 1.x) | `DeclarativeBase` + `Mapped` (SQLAlchemy 2.x) | 計画通り。2.x の型安全な宣言的マッピングを採用 |
| `datetime.utcnow()` | `datetime.now(timezone.utc)` | 計画通り。Python 3.12 で非推奨の `utcnow()` を回避 |
| `NotificationManager` を `main.py` 内に定義 | `notifications/notification_manager.py` に分離 | 計画通り。モジュール分離で保守性を向上 |
| `main.py` で inline callback に変更 | 既存の `add_handler` パターンを維持 | 計画通り。Week 1 の Observer パターンとの一貫性を保持 |
| 設計書に `alert_handler.py` なし | `alerts/alert_handler.py` を新規作成 | PriceMonitor と AlertEngine の橋渡し役が必要。型変換・エラーハンドリングを集約 |
| アラートの `id` フィールド | `name` フィールド | conditionId ベースのマッチングでは `id` は冗長。`name` で人間可読に |

---

## 3. アーキテクチャ

### データフロー

```
WebSocket → PriceMonitor → [Handler 1] DataRecorder → JSONL ファイル
                          → [Handler 2] AlertHandler → DatabaseManager → SQLite
                                                     → AlertEngine → ConditionChecker
                                                                   → NotificationManager → Telegram
                                                                                         → Discord
                                                                   → AlertLog (DB)
                                                                   → NotificationHistory (DB)
```

### DBスキーマ

```sql
-- 価格履歴
CREATE TABLE price_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id    VARCHAR(256) NOT NULL,  -- CLOBトークンID
    market      VARCHAR(256),           -- conditionId
    price       FLOAT,
    size        FLOAT,
    side        VARCHAR(10),            -- BUY/SELL
    best_bid    FLOAT,
    best_ask    FLOAT,
    timestamp   DATETIME
);

-- アラートログ
CREATE TABLE alert_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_name      VARCHAR(256) NOT NULL,
    asset_id        VARCHAR(256) NOT NULL,
    condition_type  VARCHAR(64) NOT NULL,
    threshold       FLOAT NOT NULL,
    current_value   FLOAT NOT NULL,
    message         TEXT NOT NULL,
    triggered_at    DATETIME
);

-- 通知履歴
CREATE TABLE notification_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_log_id    INTEGER NOT NULL,
    channel         VARCHAR(32) NOT NULL,   -- telegram/discord
    status          VARCHAR(16) NOT NULL,   -- success/failed/error
    error_message   TEXT,
    sent_at         DATETIME
);
```

---

## 4. 設定ファイル

### config/alerts.yaml

```yaml
alerts:
  - name: "価格急落アラート"
    market_id: "*"              # 全マーケット対象
    match_mode: "match_any"     # OR条件
    cooldown_minutes: 10
    conditions:
      - type: "price_below"
        threshold: 0.10
      - type: "price_change_percent"
        threshold_percent: -10.0
        timeframe_minutes: 5

  - name: "価格急騰アラート"
    market_id: "*"
    match_mode: "match_any"
    cooldown_minutes: 10
    conditions:
      - type: "price_above"
        threshold: 0.90
      - type: "price_change_percent"
        threshold_percent: 10.0
        timeframe_minutes: 5

  - name: "大口取引アラート"
    market_id: "*"
    match_mode: "match_any"
    cooldown_minutes: 5
    conditions:
      - type: "volume_above"
        threshold: 1000.0
```

### config/notifications.yaml

```yaml
channels:
  telegram:
    enabled: true
    # 環境変数: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
  discord:
    enabled: true
    # 環境変数: DISCORD_WEBHOOK_URL
```

---

## 5. テスト結果

```
$ pytest tests/ -v

tests/test_alert_engine.py::TestAlertEngine::test_trigger_price_below         PASSED
tests/test_alert_engine.py::TestAlertEngine::test_no_trigger_price_above      PASSED
tests/test_alert_engine.py::TestAlertEngine::test_market_specific_match       PASSED
tests/test_alert_engine.py::TestAlertEngine::test_market_specific_no_match    PASSED
tests/test_alert_engine.py::TestAlertEngine::test_cooldown                    PASSED
tests/test_alert_engine.py::TestAlertEngine::test_match_all_both_true         PASSED
tests/test_alert_engine.py::TestAlertEngine::test_match_all_partial           PASSED
tests/test_conditions.py::TestConditionChecker::test_price_below_true         PASSED
tests/test_conditions.py::TestConditionChecker::test_price_below_false        PASSED
tests/test_conditions.py::TestConditionChecker::test_price_below_equal        PASSED
tests/test_conditions.py::TestConditionChecker::test_price_above_true         PASSED
tests/test_conditions.py::TestConditionChecker::test_price_above_false        PASSED
tests/test_conditions.py::TestConditionChecker::test_price_above_equal        PASSED
tests/test_conditions.py::TestConditionChecker::test_volume_above_true        PASSED
tests/test_conditions.py::TestConditionChecker::test_volume_above_false       PASSED
tests/test_conditions.py::TestConditionChecker::test_price_change_percent_no_history   PASSED
tests/test_conditions.py::TestConditionChecker::test_price_change_percent_up           PASSED
tests/test_conditions.py::TestConditionChecker::test_price_change_percent_down         PASSED
tests/test_conditions.py::TestConditionChecker::test_price_change_percent_not_enough   PASSED
tests/test_config_loader.py::TestConfigLoader::test_load_yaml_success         PASSED
tests/test_config_loader.py::TestConfigLoader::test_load_yaml_file_not_found  PASSED
tests/test_config_loader.py::TestConfigLoader::test_get_api_credentials_success    PASSED
tests/test_config_loader.py::TestConfigLoader::test_get_api_credentials_missing    PASSED
tests/test_data_recorder.py::TestDataRecorder::test_price_change_saved        PASSED
tests/test_data_recorder.py::TestDataRecorder::test_book_saved                PASSED
tests/test_data_recorder.py::TestDataRecorder::test_trade_saved               PASSED
tests/test_data_recorder.py::TestDataRecorder::test_multiple_records_appended PASSED
tests/test_db_manager.py::TestDatabaseManager::test_save_price                PASSED
tests/test_db_manager.py::TestDatabaseManager::test_get_price_history         PASSED
tests/test_db_manager.py::TestDatabaseManager::test_get_price_history_empty   PASSED
tests/test_db_manager.py::TestDatabaseManager::test_get_price_history_time_filter  PASSED
tests/test_db_manager.py::TestDatabaseManager::test_save_alert_log            PASSED
tests/test_db_manager.py::TestDatabaseManager::test_get_last_alert_time       PASSED
tests/test_db_manager.py::TestDatabaseManager::test_get_last_alert_time_none  PASSED
tests/test_db_manager.py::TestDatabaseManager::test_save_notification_history PASSED
tests/test_db_manager.py::TestDatabaseManager::test_save_notification_history_with_error  PASSED
tests/test_price_monitor.py::TestPriceMonitor::test_handle_book_event         PASSED
tests/test_price_monitor.py::TestPriceMonitor::test_handle_price_change_wrapper    PASSED
tests/test_price_monitor.py::TestPriceMonitor::test_handle_price_change_no_asset_id  PASSED
tests/test_price_monitor.py::TestPriceMonitor::test_get_current_price_missing PASSED
tests/test_price_monitor.py::TestPriceMonitor::test_handler_callback_invoked  PASSED
tests/test_price_monitor.py::TestPriceMonitor::test_handler_error_does_not_crash   PASSED
tests/test_price_monitor.py::TestPriceMonitor::test_multiple_handlers         PASSED
tests/test_price_monitor.py::TestPriceMonitor::test_list_and_dict_both_work   PASSED

======================== 44 passed, 3 skipped in 0.16s =========================
```

- **44 テスト全パス**
- **3 テストスキップ**: API接続テスト（`POLYMARKET_API_KEY` 未設定時）
- **Week 2 新規テスト**: 27件（conditions: 11, alert_engine: 7, db_manager: 9）
- DBテストは in-memory SQLite (`:memory:`) で高速実行

---

## 6. 動作確認手順

### 起動

```bash
# 1. 環境変数設定
cp .env.example .env
# .env を編集してAPI認証情報を入力
# （任意）Telegram/Discord トークンを追加

# 2. ビルド & 起動
docker-compose up --build
```

### 確認ポイント

起動ログで以下を確認:

```
データベース初期化完了: data/polybot.db
Telegram通知: 無効（環境変数未設定）
Discord通知: 無効（環境変数未設定）
NotificationManager 初期化完了: チャンネル=なし
アラートエンジン初期化: 3 件のアラート
PriceMonitor 初期化完了
イベントハンドラー登録: handle_event    ← DataRecorder
イベントハンドラー登録: handle_event    ← AlertHandler
```

### アラートテスト

1. `config/alerts.yaml` の `threshold` を現在価格付近に調整
2. `docker-compose restart` で再起動
3. ログに `[ALERT]` が出力されることを確認
4. `data/polybot.db` にレコードが保存されていることを確認:
   ```bash
   sqlite3 data/polybot.db "SELECT COUNT(*) FROM price_history;"
   sqlite3 data/polybot.db "SELECT * FROM alert_log LIMIT 5;"
   ```

### Telegram通知テスト

1. BotFather でBot作成: https://t.me/BotFather
2. `.env` に `TELEGRAM_BOT_TOKEN` と `TELEGRAM_CHAT_ID` を設定
3. `docker-compose up --build` で再起動
4. アラート発火時にTelegramメッセージが届くことを確認

---

## 7. Week 2 完了チェックリスト

- [x] 価格データが SQLite (`price_history`) に保存される
- [x] アラート条件が正しく判定される（price_below/above, change_percent, volume_above）
- [x] match_any (OR) / match_all (AND) 条件マッチ動作
- [x] クールダウン機能が同一アラートの再送を抑制
- [x] アラートログが DB (`alert_log`) に記録される
- [x] 通知履歴が DB (`notification_history`) に記録される
- [x] Telegram/Discord が環境変数未設定時にスキップ（クラッシュしない）
- [x] 既存の DataRecorder（JSONL蓄積）が引き続き並行稼働
- [x] Week 1 の Observer パターン（`add_handler`）を維持
- [x] 全テスト通過（44 passed, 3 skipped）

---

## 8. 次のステップ（Week 3 に向けて）

- 取引シグナル検出ロジックの実装
- CLOB認証クライアントによる注文発行
- ポジション管理・リスク制御
- バックテスト用データ（JSONL + SQLite）の活用
