"""FastAPI Web 管理画面 API

ポジション確認・取引履歴・パフォーマンス・バックテスト実行を提供。
"""
import importlib.util
import os
import re
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel

from database.db_manager import DatabaseManager
from executor.position_manager import PositionManager
from executor.order_executor import OrderExecutor
from notifications.notification_manager import NotificationManager
from backtester.data_fetcher import DataFetcher
from backtester.backtest_engine import BacktestEngine
from backtester.performance_analyzer import PerformanceAnalyzer

app = FastAPI(title="Polybot Web API", version="1.0.0")

# 開発用: Reactからのアクセスを許可
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# グローバル参照（startup で初期化）
_db_manager: Optional[DatabaseManager] = None
_position_manager: Optional[PositionManager] = None
_order_executor: Optional[OrderExecutor] = None
_notification_manager: Optional[NotificationManager] = None
_dry_run: bool = True


class DryRunRequest(BaseModel):
    enabled: bool


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


_LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(\w+)\s*\|\s*(.+)$"
)


def _parse_log_line(line: str) -> Optional[dict]:
    """ログ行をパースして dict に変換"""
    m = _LOG_PATTERN.match(line.strip())
    if not m:
        return None
    return {
        "timestamp": m.group(1),
        "level": m.group(2).strip(),
        "message": m.group(3).strip(),
    }


@app.on_event("startup")
def startup_event():
    """アプリケーション起動時の初期化"""
    global _db_manager, _position_manager, _order_executor, _notification_manager
    _db_manager = DatabaseManager()
    _position_manager = PositionManager(_db_manager)
    _order_executor = OrderExecutor(_db_manager)
    try:
        _notification_manager = NotificationManager(_db_manager)
    except Exception as e:
        logger.warning(f"通知マネージャー初期化失敗: {e}")
    logger.info("Web API 起動完了")


@app.get("/api/status")
def get_status():
    """システムステータス"""
    daily_pnl = 0.0
    total_assets_usdc = 0.0

    if _db_manager is not None:
        daily_pnl = _db_manager.get_daily_pnl()
        positions = _db_manager.get_all_positions()
        total_assets_usdc = sum(p.size_usdc for p in positions)

    return {
        "status": "running",
        "version": "1.0.0",
        "daily_pnl": round(daily_pnl, 6),
        "total_assets_usdc": round(total_assets_usdc, 6),
        "dry_run": _dry_run,
    }


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


@app.get("/api/logs")
def get_logs(
    limit: int = Query(default=100, ge=1, le=1000),
    level: Optional[str] = Query(default=None),
):
    """ログ取得（最新のログファイルから末尾を読み取り）"""
    log_dir = Path("logs")
    if not log_dir.exists():
        return {"logs": [], "count": 0}

    # 最新のログファイルを探す
    log_files = sorted(log_dir.glob("polybot_*.log"), reverse=True)
    if not log_files:
        return {"logs": [], "count": 0}

    entries: list[dict] = []
    for log_file in log_files:
        if len(entries) >= limit:
            break
        try:
            lines = log_file.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        for line in reversed(lines):
            if len(entries) >= limit:
                break
            parsed = _parse_log_line(line)
            if parsed is None:
                continue
            if level and parsed["level"] != level.upper():
                continue
            entries.append(parsed)

    # 時系列順に並べ替え
    entries.reverse()

    return {"logs": entries, "count": len(entries)}


@app.post("/api/config/dry_run")
def set_dry_run(req: DryRunRequest):
    """ドライランモードの切り替え"""
    global _dry_run
    _dry_run = req.enabled
    if _order_executor is not None:
        _order_executor.live_trading = not req.enabled
    return {
        "dry_run": _dry_run,
        "message": f"Dry-run mode {'enabled' if _dry_run else 'disabled'}",
    }


@app.post("/api/control/panic_close")
def panic_close():
    """全ポジションを強制クローズしドライランモードを有効化"""
    global _dry_run
    closed = 0
    if _db_manager is not None:
        positions = _db_manager.get_all_positions()
        for p in positions:
            _db_manager.delete_position(p.asset_id)
            closed += 1
    _dry_run = True
    if _order_executor is not None:
        _order_executor.live_trading = False
    return {
        "success": True,
        "closed_positions": closed,
        "message": f"Panic close executed. {closed} position(s) closed. Dry-run mode activated.",
    }


@app.post("/api/control/test_notification")
async def test_notification():
    """テスト通知を送信"""
    if _notification_manager is None:
        return {"success": False, "message": "Notification manager not initialized"}
    try:
        await _notification_manager.send_alert(
            alert_log_id=0,
            market_name="TEST",
            price="0.00",
            condition="test",
            message="This is a test notification from Polybot dashboard.",
        )
        return {"success": True, "message": "Test notification sent"}
    except Exception as e:
        return {"success": False, "message": f"Failed to send notification: {e}"}


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
        "equity_curve": results.get("equity_curve", []),
        "trades": results.get("trades", []),
    }


# フロントエンドのビルド成果物ディレクトリ
_frontend_dir = os.path.join(os.path.dirname(__file__), "frontend", "dist")

# ディレクトリが存在する場合のみマウント (開発中のエラー防止)
if os.path.exists(_frontend_dir):
    # アセットファイル (JS/CSS) を /assets で配信
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_dir, "assets")), name="assets")

    # SPA対応: API以外のパスへのアクセスはすべて index.html を返す
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # APIへのリクエストは除外
        if full_path.startswith("api") or full_path.startswith("docs"):
            return {"error": "Not Found"}

        # ファイルが存在すればそれを返す (favicon.icoなど)
        file_path = os.path.join(_frontend_dir, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)

        # それ以外は React の index.html を返す
        return FileResponse(os.path.join(_frontend_dir, "index.html"))
else:
    logger.warning(f"Frontend build not found at {_frontend_dir}. Web UI will not be available.")
