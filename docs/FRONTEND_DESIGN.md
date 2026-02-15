# PolyBot Framework - Frontend Design Document

**Version:** 1.0
**Date:** 2026-02-14
**Status:** Draft

---

## 1. コンセプトと設計思想

### 1.1 "Zero Configuration" UX
PolyBotの強みである「Docker一発起動」の体験を損なわないため、フロントエンドは独立したサーバープロセスではなく、**FastAPIバックエンドによって静的配信されるSPA (Single Page Application)** として構築する。
ユーザーは別途 Node.js 環境を用意する必要がない。

### 1.2 "Pro-Trader" UI
投資ツールとして信頼性を担保するため、以下のUI要件を満たす。
* **Dark Mode Native**: 長時間の監視でも目が疲れないダークテーマを標準とする。
* **Data Density**: 必要な情報（価格、ポジション、ログ）を一画面に凝縮する。
* **Responsive**: PCでの分析だけでなく、外出先（スマホ）からのステータス確認に対応する。

### 1.3 拡張性 (Scalability)
将来的な機能拡張（TradingViewチャートの埋め込み、ドラッグ＆ドロップでの戦略編集など）に耐えうるよう、**React + TypeScript** のモダンなエコシステムを採用する。

---

## 2. 技術スタック

### Core Framework
* **React 18**: コンポーネント指向による高い再利用性と拡張性。
* **TypeScript**: 型安全性によるバグの抑制と、バックエンド(Pydantic)とのデータ構造の同期。
* **Vite**: 高速なビルドツール。開発体験の向上。

### UI Library & Styling
* **Chakra UI (or Mantine)**:
    * 選定理由: 開発スピードが非常に速い。ダークモード対応が標準装備。
    * カスタマイズ性が高く、"ダッシュボード"系のコンポーネントが豊富。
* **Recharts**:
    * 選定理由: Reactに特化したチャートライブラリ。バックテスト結果の描画に使用。

### State Management & Data Fetching
* **TanStack Query (React Query)**:
    * 選定理由: サーバー状態（APIデータ）の管理に特化。
    * Auto Refetch（ポーリング）機能により、WebSocketサーバーを別途立てずとも「ほぼリアルタイム」な監視画面を容易に実装できる。
* **Zustand**:
    * 選定理由: クライアント状態（UI設定など）の管理用。Reduxより軽量でシンプル。

---

## 3. アーキテクチャ

### 3.1 構成図

```mermaid
graph LR
    User[Browser] -- HTTP Request --> FastAPI[FastAPI Server :8000]
    subgraph Docker Container
        FastAPI -- Serve --> StaticFiles[React Build (/app/static)]
        FastAPI -- API JSON --> Endpoints[API Endpoints (/api/v1)]
        Endpoints -- Query --> SQLite[(Database)]
        Endpoints -- Action --> BotProcess[Bot Logic]
    end
3.2 ディレクトリ構成案
src/web/ 配下を以下のように拡張する。
Plaintext
src/web/
├── api.py                  # 既存のAPI定義
├── templates/              # (廃止 または Reactのマウント用HTML)
└── frontend/               # NEW: Reactプロジェクトルート
    ├── package.json
    ├── vite.config.ts
    ├── src/
    │   ├── components/     # 共通UIパーツ (Button, Card...)
    │   ├── features/       # 機能ごとの構成
    │   │   ├── dashboard/  # ダッシュボード画面
    │   │   ├── backtest/   # バックテスト画面
    │   │   └── settings/   # 設定画面
    │   ├── hooks/          # カスタムHooks
    │   ├── api/            # APIクライアント (Axios/Fetch)
    │   └── types/          # TypeScript型定義 (FastAPIと合わせる)
    └── dist/               # Build成果物 (これをFastAPIが配信)

4. 画面設計と機能要件
4.1 Dashboard (ホーム画面)
システムの稼働状況を一目で把握するコックピット。
Status Panel:
Bot稼働状態 (Running / Stopped)
現在の合計資産 (USDC)
本日の損益 (PnL)
Live Ticker:
監視中のマーケット名と現在価格（緑/赤で変動表示）。
Active Positions:
保有中のポジション一覧（数量、平均取得単価、評価損益）。
System Logs:
最新のログ100件をスクロール表示（Auto-scroll機能付き）。
4.2 Backtest Runner (検証画面)
Week 4で実装したバックテスト機能をGUIから実行する。
Config Form:
期間設定 (DatePicker)
対象マーケット選択 (Dropdown)
初期資金設定 (Input)
Result Viewer:
Equity Curve: 資産推移のラインチャート (Recharts)。
Metrics: シャープレシオ、最大ドローダウン等の統計カード。
Trade List: 取引履歴のテーブル表示。
4.3 Strategy Editor (上級者向け・将来拡張)
Code Editor:
Monaco Editor (VSCodeのWeb版) を埋め込み、ブラウザ上で strategy.py を直接編集・保存できるようにする。

5. API連携設計
バックエンド (api.py) に以下のエンドポイント拡充を推奨。
Method
Endpoint
Description
Frontend Usage
GET
/api/status
Botの稼働状況と基本メトリクス
Dashboard (Polling 5s)
GET
/api/logs
最新ログの取得
Dashboard Log (Polling 2s)
POST
/api/control/{action}
start/stop/restart
Status Panel Buttons
POST
/api/backtest/run
バックテスト実行 (非同期)
Backtest Runner
GET
/api/backtest/history
過去のバックテスト結果一覧
Backtest History
GET
/api/config/strategy
現在の戦略コード取得
Strategy Editor
POST
/api/config/strategy
戦略コードの上書き保存
Strategy Editor


6. 実装フェーズ
Phase 1: MVP Frontend (Day 1-2)
React + Vite 環境構築。
FastAPIによる静的ファイル配信設定。
Dashboard: ステータス表示とログ表示のみ実装。
Backtest: 実行ボタンと、結果画像(equity_curve.png)の表示のみ。
Phase 2: Interactive Features (Day 3-5)
Recharts導入: バックテスト結果を画像ではなくインタラクティブなグラフにする。
Configuration: 設定ファイル(config.yaml)をGUIフォームで編集可能にする。
Phase 3: Advanced (Future)
Monaco Editor によるコード編集。
WebSocket導入による完全リアルタイム化。

7. ユーザーへの提供方法
開発時: 開発者は npm run build を実行して dist/ を生成する。
配布時: 生成された dist/ フォルダの中身（HTML/JS/CSS）をGitリポジトリに含める（またはDockerビルド時に生成する）。
ユーザー:
ユーザーは npm をインストールする必要がない。
いつもの通り docker-compose up するだけで、Python側がビルド済みのReactアプリを配信する。
Python
# src/web/api.py の実装イメージ
from fastapi.staticfiles import StaticFiles

app.mount("/", StaticFiles(directory="src/web/frontend/dist", html=True), name="static")

PolyBot Framework - Providing Professional Tools for Everyone

---

### 💡 補足: なぜこの構成が「ユーザーにとって最適」なのか？

* **導入コストゼロ**: ユーザーは「Web画面のためにNode.jsを入れてください」と言われると離脱します。この構成なら、PythonとDockerだけで完結します。
* **動作の軽快さ**: サーバーサイドレンダリングや複雑なテンプレートエンジンを使わず、ブラウザ側で描画するため、操作感がネイティブアプリのようにサクサクになります。
* **スマホ対応**: Chakra UIなどのレスポンシブ対応ライブラリを使うことで、追加工数なしで「出先からスマホでボット停止」などの操作が可能になります。

この設計書に基づいて、まずは **Phase 1** の実装に進むことをお勧めします。
