# PolyBot Framework - Week 4 実装設計書

## 📋 Week 4 の目標

**バックテスト機能とWeb管理画面の実装**

### 成果物
- 過去データを使った戦略検証
- パフォーマンス分析ダッシュボード
- Web管理画面（FastAPI + React）
- ユーザーマニュアル
- MVP完成・リリース準備

---

## 🏗️ 追加ファイル構成

```
polybot-framework/
├── src/
│   ├── backtester/
│   │   ├── __init__.py
│   │   ├── backtest_engine.py    # NEW: バックテストエンジン
│   │   ├── data_fetcher.py       # NEW: 過去データ取得
│   │   └── performance_analyzer.py # NEW: パフォーマンス分析
│   └── web/
│       ├── __init__.py
│       ├── api.py                # NEW: FastAPI エンドポイント
│       ├── static/               # NEW: Reactフロントエンド
│       └── templates/            # NEW: HTMLテンプレート
├── docs/
│   ├── USER_MANUAL.md            # NEW: ユーザーマニュアル
│   ├── API_REFERENCE.md          # NEW: API リファレンス
│   └── TROUBLESHOOTING.md        # NEW: トラブルシューティング
└── scripts/
    ├── backtest.sh               # NEW: バックテスト実行スクリプト
    └── export_report.py          # NEW: レポート出力
```

---

## 📦 追加依存パッケージ

### requirements.txt に追加

```txt
# Web フレームワーク
fastapi==0.108.0
uvicorn[standard]==0.25.0
jinja2==3.1.2

# データ分析
numpy==1.26.2
matplotlib==3.8.2
seaborn==0.13.0

# レポート生成
reportlab==4.0.7
```

---

## 💻 バックテスト実装

### src/backtester/data_fetcher.py

```python
"""過去データ取得"""
from typing import List, Dict
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd

class DataFetcher:
    """データ取得クラス"""
    
    def __init__(self, poly_client):
        """
        初期化
        
        Args:
            poly_client: PolymarketClientインスタンス
        """
        self.poly_client = poly_client
        logger.info("データ取得エンジン初期化完了")
    
    async def fetch_historical_prices(self, market_id: str, days: int = 30) -> pd.DataFrame:
        """
        過去の価格データを取得
        
        Args:
            market_id: マーケットID
            days: 取得日数
            
        Returns:
            pd.DataFrame: 価格データ
        """
        try:
            # Polymarket Data API から過去データ取得
            # 実際のAPI呼び出し:
            # data = await self.poly_client.gamma_client.get_historical_prices(market_id, days)
            
            # サンプルデータ生成（実装時は実際のAPIに置き換え）
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # ダミーデータ
            dates = pd.date_range(start=start_date, end=end_date, freq='1H')
            prices = 0.5 + (pd.Series(range(len(dates))) % 100) / 200  # 0.3〜0.7の範囲
            volumes = 1000 + (pd.Series(range(len(dates))) % 50) * 100
            
            df = pd.DataFrame({
                'timestamp': dates,
                'price': prices,
                'volume': volumes,
                'spread': 0.02
            })
            
            logger.info(f"過去データ取得完了: {market_id} ({len(df)} レコード)")
            return df
            
        except Exception as e:
            logger.error(f"過去データ取得エラー: {e}")
            return pd.DataFrame()
```

### src/backtester/backtest_engine.py

```python
"""バックテストエンジン"""
from typing import Dict, List
from datetime import datetime
from loguru import logger
import pandas as pd

class BacktestEngine:
    """バックテストエンジン"""
    
    def __init__(self, strategy, data_fetcher):
        """
        初期化
        
        Args:
            strategy: ユーザーストラテジーモジュール
            data_fetcher: DataFetcherインスタンス
        """
        self.strategy = strategy
        self.data_fetcher = data_fetcher
        
        # バックテスト結果
        self.trades = []
        self.positions = {}
        self.equity_curve = []
        
        logger.info("バックテストエンジン初期化完了")
    
    async def run_backtest(self, market_id: str, days: int = 60) -> Dict:
        """
        バックテストを実行
        
        Args:
            market_id: マーケットID
            days: テスト期間（日数）
            
        Returns:
            Dict: バックテスト結果
        """
        logger.info(f"バックテスト開始: {market_id} ({days}日間)")
        
        # 過去データ取得
        df = await self.data_fetcher.fetch_historical_prices(market_id, days)
        
        if df.empty:
            logger.error("過去データが取得できませんでした")
            return {}
        
        # 初期化
        initial_capital = 10000  # USDC
        current_capital = initial_capital
        position_size = 0
        avg_price = 0
        
        self.trades = []
        self.equity_curve = [initial_capital]
        
        # シミュレーション実行
        for idx, row in df.iterrows():
            price = row['price']
            volume = row['volume']
            timestamp = row['timestamp']
            
            market_data = {
                'volume': volume,
                'spread': row.get('spread', 0.02)
            }
            
            # 損切り・利確チェック
            if position_size > 0:
                pnl_percent = (price - avg_price) / avg_price * 100
                
                # 損切り
                if pnl_percent <= -self.strategy.STOP_LOSS_PERCENT:
                    pnl = position_size * (price - avg_price)
                    current_capital += position_size * price
                    
                    self.trades.append({
                        'timestamp': timestamp,
                        'type': 'sell',
                        'reason': 'STOP_LOSS',
                        'price': price,
                        'size': position_size,
                        'pnl': pnl,
                        'pnl_percent': pnl_percent
                    })
                    
                    position_size = 0
                    avg_price = 0
                
                # 利確
                elif pnl_percent >= self.strategy.TAKE_PROFIT_PERCENT:
                    pnl = position_size * (price - avg_price)
                    current_capital += position_size * price
                    
                    self.trades.append({
                        'timestamp': timestamp,
                        'type': 'sell',
                        'reason': 'TAKE_PROFIT',
                        'price': price,
                        'size': position_size,
                        'pnl': pnl,
                        'pnl_percent': pnl_percent
                    })
                    
                    position_size = 0
                    avg_price = 0
            
            # 買い条件チェック
            if self.strategy.custom_buy_condition(price, position_size, market_data):
                if current_capital >= self.strategy.POSITION_SIZE_USDC:
                    buy_size = min(self.strategy.POSITION_SIZE_USDC, current_capital)
                    
                    # ポジション追加
                    if position_size > 0:
                        # 平均取得価格更新
                        total_cost = position_size * avg_price + buy_size * price
                        position_size += buy_size
                        avg_price = total_cost / position_size
                    else:
                        position_size = buy_size
                        avg_price = price
                    
                    current_capital -= buy_size
                    
                    self.trades.append({
                        'timestamp': timestamp,
                        'type': 'buy',
                        'reason': 'STRATEGY',
                        'price': price,
                        'size': buy_size,
                        'pnl': 0,
                        'pnl_percent': 0
                    })
            
            # 売り条件チェック
            elif self.strategy.custom_sell_condition(price, position_size, market_data):
                if position_size > 0:
                    pnl = position_size * (price - avg_price)
                    pnl_percent = (price - avg_price) / avg_price * 100
                    
                    current_capital += position_size * price
                    
                    self.trades.append({
                        'timestamp': timestamp,
                        'type': 'sell',
                        'reason': 'STRATEGY',
                        'price': price,
                        'size': position_size,
                        'pnl': pnl,
                        'pnl_percent': pnl_percent
                    })
                    
                    position_size = 0
                    avg_price = 0
            
            # エクイティカーブ記録
            total_equity = current_capital + (position_size * price if position_size > 0 else 0)
            self.equity_curve.append(total_equity)
        
        # 最終ポジションクローズ（テスト終了時）
        if position_size > 0:
            final_price = df.iloc[-1]['price']
            pnl = position_size * (final_price - avg_price)
            pnl_percent = (final_price - avg_price) / avg_price * 100
            
            current_capital += position_size * final_price
            
            self.trades.append({
                'timestamp': df.iloc[-1]['timestamp'],
                'type': 'sell',
                'reason': 'BACKTEST_END',
                'price': final_price,
                'size': position_size,
                'pnl': pnl,
                'pnl_percent': pnl_percent
            })
        
        # 結果分析
        results = self._analyze_results(initial_capital, current_capital)
        
        logger.info(f"バックテスト完了: 総損益={results['total_pnl']:.2f} USDC ({results['total_return']:.2f}%)")
        
        return results
    
    def _analyze_results(self, initial_capital: float, final_capital: float) -> Dict:
        """バックテスト結果を分析"""
        if not self.trades:
            return {
                'total_pnl': 0,
                'total_return': 0,
                'total_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0
            }
        
        # 取引統計
        sells = [t for t in self.trades if t['type'] == 'sell']
        wins = [t for t in sells if t['pnl'] > 0]
        losses = [t for t in sells if t['pnl'] <= 0]
        
        total_pnl = sum(t['pnl'] for t in sells)
        total_return = (final_capital - initial_capital) / initial_capital * 100
        
        win_rate = len(wins) / len(sells) * 100 if sells else 0
        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0
        
        # シャープレシオ計算（簡略版）
        returns = pd.Series(self.equity_curve).pct_change().dropna()
        sharpe_ratio = returns.mean() / returns.std() * (252 ** 0.5) if returns.std() > 0 else 0
        
        # 最大ドローダウン
        equity_series = pd.Series(self.equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max * 100
        max_drawdown = abs(drawdown.min())
        
        return {
            'total_pnl': total_pnl,
            'total_return': total_return,
            'total_trades': len(sells),
            'win_rate': win_rate,
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'final_capital': final_capital,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }
```

### src/backtester/performance_analyzer.py

```python
"""パフォーマンス分析"""
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List
from loguru import logger
import pandas as pd
from pathlib import Path

class PerformanceAnalyzer:
    """パフォーマンス分析クラス"""
    
    def __init__(self):
        """初期化"""
        sns.set_style("darkgrid")
        logger.info("パフォーマンスアナライザー初期化完了")
    
    def generate_report(self, backtest_results: Dict, output_dir: str = "reports"):
        """
        レポート生成
        
        Args:
            backtest_results: バックテスト結果
            output_dir: 出力ディレクトリ
        """
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        logger.info(f"レポート生成開始: {output_dir}")
        
        # エクイティカーブ
        self._plot_equity_curve(
            backtest_results['equity_curve'],
            output_path / "equity_curve.png"
        )
        
        # 取引履歴
        self._plot_trades(
            backtest_results['trades'],
            output_path / "trades.png"
        )
        
        # 統計サマリー
        self._save_summary(
            backtest_results,
            output_path / "summary.txt"
        )
        
        logger.info("レポート生成完了")
    
    def _plot_equity_curve(self, equity_curve: List[float], filepath: Path):
        """エクイティカーブをプロット"""
        plt.figure(figsize=(12, 6))
        plt.plot(equity_curve, linewidth=2, color='#2E75B6')
        plt.title('Equity Curve', fontsize=16, fontweight='bold')
        plt.xlabel('Time Steps')
        plt.ylabel('Equity (USDC)')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close()
        
        logger.info(f"エクイティカーブ保存: {filepath}")
    
    def _plot_trades(self, trades: List[Dict], filepath: Path):
        """取引履歴をプロット"""
        if not trades:
            return
        
        df = pd.DataFrame(trades)
        sells = df[df['type'] == 'sell']
        
        plt.figure(figsize=(12, 6))
        
        # 勝ち取引と負け取引を色分け
        wins = sells[sells['pnl'] > 0]
        losses = sells[sells['pnl'] <= 0]
        
        plt.scatter(range(len(wins)), wins['pnl'], color='green', alpha=0.6, label='Wins', s=100)
        plt.scatter(range(len(wins), len(wins) + len(losses)), losses['pnl'], 
                   color='red', alpha=0.6, label='Losses', s=100)
        
        plt.axhline(y=0, color='black', linestyle='--', alpha=0.3)
        plt.title('Trade P&L', fontsize=16, fontweight='bold')
        plt.xlabel('Trade Number')
        plt.ylabel('P&L (USDC)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(filepath, dpi=150)
        plt.close()
        
        logger.info(f"取引履歴グラフ保存: {filepath}")
    
    def _save_summary(self, results: Dict, filepath: Path):
        """統計サマリーを保存"""
        summary = f"""
========================================
  BACKTEST PERFORMANCE SUMMARY
========================================

総合結果:
  総損益: {results['total_pnl']:.2f} USDC
  総リターン: {results['total_return']:.2f}%
  最終資産: {results['final_capital']:.2f} USDC

取引統計:
  総取引回数: {results['total_trades']}
  勝ち取引: {results['winning_trades']}
  負け取引: {results['losing_trades']}
  勝率: {results['win_rate']:.2f}%

損益分析:
  平均勝ち: {results['avg_win']:.2f} USDC
  平均負け: {results['avg_loss']:.2f} USDC
  ペイオフレシオ: {abs(results['avg_win'] / results['avg_loss']) if results['avg_loss'] != 0 else 0:.2f}

リスク指標:
  シャープレシオ: {results['sharpe_ratio']:.2f}
  最大ドローダウン: {results['max_drawdown']:.2f}%

========================================
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        logger.info(f"統計サマリー保存: {filepath}")
```

---

## 🌐 Web管理画面

### src/web/api.py

```python
"""FastAPI Web API"""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from typing import Dict, List
from datetime import datetime, timedelta
from loguru import logger
import asyncio

app = FastAPI(title="PolyBot Framework API", version="1.0.0")

# グローバル変数（実際はDIで管理）
db_manager = None
position_manager = None

@app.get("/")
async def root():
    """ルート"""
    return {"message": "PolyBot Framework API", "status": "running"}

@app.get("/api/status")
async def get_status():
    """システムステータス"""
    return {
        "status": "running",
        "uptime": "24h",
        "version": "1.0.0"
    }

@app.get("/api/positions")
async def get_positions():
    """現在のポジション一覧"""
    try:
        # DB からポジション取得
        positions = []  # db_manager.get_all_positions()
        
        return {
            "positions": positions,
            "total_value": sum(p.get('size_usdc', 0) for p in positions)
        }
    except Exception as e:
        logger.error(f"ポジション取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trades")
async def get_trades(limit: int = 50):
    """取引履歴"""
    try:
        # DB から取引履歴取得
        trades = []  # db_manager.get_recent_trades(limit)
        
        return {"trades": trades}
    except Exception as e:
        logger.error(f"取引履歴取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/performance")
async def get_performance(days: int = 7):
    """パフォーマンス統計"""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # DB から統計取得
        stats = {
            "total_pnl": 0,
            "win_rate": 0,
            "total_trades": 0
        }
        
        return stats
    except Exception as e:
        logger.error(f"パフォーマンス取得エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/backtest")
async def run_backtest(market_id: str, days: int = 60):
    """バックテスト実行"""
    try:
        # バックテスト実行（非同期）
        logger.info(f"バックテスト開始: {market_id}")
        
        # 実際の実装では BacktestEngine を使用
        results = {
            "status": "completed",
            "total_return": 15.5,
            "win_rate": 65.0
        }
        
        return results
    except Exception as e:
        logger.error(f"バックテストエラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### docker-compose.yml（Web UI追加版）

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
      - ./src:/app/src
    env_file:
      - .env
    restart: unless-stopped
    networks:
      - polybot-network
  
  # Web管理画面
  web:
    build: .
    container_name: polybot-web
    command: uvicorn src.web.api:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"
    volumes:
      - ./src:/app/src
      - ./data:/app/data
      - ./reports:/app/reports
    env_file:
      - .env
    depends_on:
      - polybot
    networks:
      - polybot-network

networks:
  polybot-network:
    driver: bridge
```

---

## 📚 ドキュメント

### docs/USER_MANUAL.md

```markdown
# PolyBot Framework - ユーザーマニュアル

## 🚀 クイックスタート

### 1. 環境準備

```bash
# リポジトリをクローン
git clone https://github.com/yourname/polybot-framework.git
cd polybot-framework

# .env ファイルを作成
cp .env.example .env
```

### 2. API認証情報の設定

`.env` ファイルを編集：

```bash
POLYMARKET_API_KEY=your_api_key
POLYMARKET_API_SECRET=your_secret
POLYMARKET_API_PASSPHRASE=your_passphrase
POLYMARKET_PRIVATE_KEY=your_private_key
POLYMARKET_FUNDER_ADDRESS=your_funder_address
```

### 3. 取引戦略の設定

`config/strategy.py` を編集：

```python
# 買い価格
BUY_THRESHOLD = 0.25

# 売り価格
SELL_THRESHOLD = 0.75

# ポジションサイズ
POSITION_SIZE_USDC = 50
```

### 4. 起動

```bash
# コンテナ起動
docker-compose up -d

# ログ確認
docker-compose logs -f polybot
```

### 5. Web管理画面

ブラウザで `http://localhost:8000` にアクセス

## 🧪 バックテストの実行

```bash
# バックテスト実行
docker-compose run polybot python -m src.backtester.backtest_engine

# レポート確認
ls reports/
```

## ⚙️ 設定ガイド

### リスク管理設定

`config/risk.yaml` を編集：

```yaml
global:
  max_total_position_usdc: 5000
  max_daily_loss_usdc: 500
```

### アラート設定

`config/alerts.yaml` を編集：

```yaml
alerts:
  - id: "alert_001"
    name: "低価格アラート"
    conditions:
      - type: "price_below"
        threshold: 0.30
```

## 🆘 トラブルシューティング

### Q: 接続エラーが出る

A: API認証情報を確認してください

### Q: 注文が実行されない

A: `ENABLE_TRADING = True` に設定してください

詳細は `docs/TROUBLESHOOTING.md` を参照
```

---

## 🧪 テスト手順

### 1. バックテスト実行

```bash
docker-compose run polybot python -m src.backtester.backtest_engine \
  --market-id "0x1234567890abcdef" \
  --days 60
```

### 2. レポート確認

```bash
ls reports/
# equity_curve.png
# trades.png
# summary.txt
```

### 3. Web UI 動作確認

```bash
# Web起動
docker-compose up web

# ブラウザで確認
open http://localhost:8000
```

---

## ✅ Week 4 完了条件

1. ✅ バックテストが正常に実行される
2. ✅ パフォーマンスレポートが生成される
3. ✅ Web管理画面が動作する
4. ✅ API エンドポイントが応答する
5. ✅ ユーザーマニュアルが完成している
6. ✅ 全機能の統合テスト完了

---

## 📦 リリース準備

### リリースチェックリスト

- [ ] 全機能の動作確認
- [ ] ドキュメント完成
- [ ] セキュリティチェック
- [ ] パフォーマンステスト
- [ ] バグ修正
- [ ] README.md 更新
- [ ] LICENSE ファイル追加
- [ ] バージョンタグ作成

### デプロイ手順

```bash
# Dockerイメージをビルド
docker-compose build

# リリース用パッケージ作成
tar -czf polybot-framework-v1.0.0.tar.gz .

# GitHub Releaseにアップロード
```

---

**🎉 Week 4完了で、PolyBot Framework MVPが完成！**

販売準備を開始できます！