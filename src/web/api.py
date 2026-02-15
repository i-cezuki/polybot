"""FastAPI Web 管理画面 API

ポジション確認・取引履歴・パフォーマンス・バックテスト実行を提供。
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from loguru import logger

from database.db_manager import DatabaseManager
from executor.position_manager import PositionManager
from backtester.data_fetcher import DataFetcher
from backtester.backtest_engine import BacktestEngine
from backtester.performance_analyzer import PerformanceAnalyzer

app = FastAPI(title="Polybot Web API", version="1.0.0")

# グローバル参照（startup で初期化）
_db_manager: Optional[DatabaseManager] = None
_position_manager: Optional[PositionManager] = None


def _load_calculate_signal(strategy_path: str = "config/strategy.py"):
    """config/strategy.py から calculate_signal を動的ロード"""
    path = Path(strategy_path)
    if not path.exists():
        logger.warning(f"戦略ファイルが見つかりません: {strategy_path}")
        return None

    try:
        spec = importlib.util.spec_from_file_location("user_strategy", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "calculate_signal"):
            return module.calculate_signal
        logger.warning(f"calculate_signal() が見つかりません: {strategy_path}")
    except Exception as e:
        logger.error(f"戦略ロードエラー: {e}")
    return None


@app.on_event("startup")
def startup_event():
    """アプリケーション起動時の初期化"""
    global _db_manager, _position_manager
    _db_manager = DatabaseManager()
    _position_manager = PositionManager(_db_manager)
    logger.info("Web API 起動完了")


@app.get("/")
def root():
    """ルートエンドポイント"""
    return {"message": "Polybot Web API", "status": "running"}


@app.get("/api/status")
def get_status():
    """システムステータス"""
    return {"status": "running", "version": "1.0.0"}


@app.get("/api/positions")
def get_positions():
    """アクティブポジション一覧"""
    if _db_manager is None:
        return {"positions": [], "total_value_usdc": 0.0}

    positions = _db_manager.get_all_positions()
    pos_list = []
    total_value = 0.0

    for p in positions:
        pos_list.append({
            "asset_id": p.asset_id,
            "market": p.market,
            "side": p.side,
            "size_usdc": p.size_usdc,
            "average_price": p.average_price,
            "realized_pnl": p.realized_pnl,
            "opened_at": p.opened_at.isoformat() if p.opened_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        })
        total_value += p.size_usdc

    return {"positions": pos_list, "total_value_usdc": round(total_value, 6)}


@app.get("/api/trades")
def get_trades(
    limit: int = Query(default=100, ge=1, le=1000),
    since_hours: int = Query(default=24, ge=1, le=720),
):
    """取引履歴"""
    if _db_manager is None:
        return {"trades": [], "count": 0}

    since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    trades = _db_manager.get_trades_since(since)

    trade_list = []
    for t in trades[:limit]:
        trade_list.append({
            "id": t.id,
            "asset_id": t.asset_id,
            "market": t.market,
            "action": t.action,
            "price": t.price,
            "amount_usdc": t.amount_usdc,
            "simulated": t.simulated,
            "realized_pnl": t.realized_pnl,
            "reason": t.reason,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })

    return {"trades": trade_list, "count": len(trade_list)}


@app.get("/api/performance")
def get_performance(
    days: int = Query(default=7, ge=1, le=365),
):
    """パフォーマンスサマリー"""
    if _db_manager is None:
        return {"total_pnl": 0.0, "win_rate": 0.0, "total_trades": 0}

    since = datetime.now(timezone.utc) - timedelta(days=days)
    trades = _db_manager.get_trades_since(since)

    sell_trades = [t for t in trades if t.action == "SELL"]
    total_trades = len(sell_trades)
    total_pnl = sum(t.realized_pnl or 0.0 for t in sell_trades)

    winning = sum(1 for t in sell_trades if (t.realized_pnl or 0) > 0)
    win_rate = (winning / total_trades * 100) if total_trades > 0 else 0.0

    return {
        "total_pnl": round(total_pnl, 6),
        "win_rate": round(win_rate, 2),
        "total_trades": total_trades,
        "winning_trades": winning,
        "losing_trades": total_trades - winning,
        "period_days": days,
    }


@app.post("/api/backtest")
def run_backtest(
    market_id: Optional[str] = Query(default=None),
    days: int = Query(default=7, ge=1, le=90),
    initial_capital: float = Query(default=10000.0, ge=100),
):
    """バックテスト実行"""
    # 戦略ロード
    calc_signal = _load_calculate_signal()
    if calc_signal is None:
        return {"error": "戦略ファイルをロードできません"}

    # データ取得
    fetcher = DataFetcher(data_dir="data", db_manager=_db_manager)

    from datetime import date
    end_date = date.today().isoformat()
    start_date = (date.today() - timedelta(days=days)).isoformat()

    ticks = fetcher.load_jsonl_files(
        market_id=market_id,
        start_date=start_date,
        end_date=end_date,
    )

    if not ticks and _db_manager is not None and market_id:
        ticks = fetcher.load_from_db(market_id, minutes=days * 1440)

    if not ticks:
        return {"error": "バックテスト用データがありません", "ticks_count": 0}

    # バックテスト実行
    engine = BacktestEngine(
        calculate_signal=calc_signal,
        initial_capital=initial_capital,
    )
    results = engine.run(ticks)

    # 分析
    analyzer = PerformanceAnalyzer()
    analysis = analyzer.analyze(results)

    # レポート生成
    try:
        analyzer.generate_report_with_charts(analysis, results)
    except Exception as e:
        logger.warning(f"レポート生成エラー: {e}")

    return {
        "ticks_count": len(ticks),
        "analysis": analysis,
        "trades_count": len(results.get("trades", [])),
    }
