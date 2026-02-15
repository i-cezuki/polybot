"""注文実行モジュール（Week 3: シミュレーションのみ）"""
import os
from typing import Optional

from loguru import logger

from database.db_manager import DatabaseManager


class OrderExecutor:
    """注文実行クラス

    Week 3 は全てシミュレーション（DBに Trade 記録のみ）。
    ENABLE_TRADING 環境変数で将来のライブ切替に備える。

    スリッページ:
      - use_book_price=True の場合、BUY は best_ask、SELL は best_bid を基準価格とする
      - slippage_bps で追加スリッページを適用（BUYは高く、SELLは安く約定）
    """

    def __init__(self, db_manager: DatabaseManager, slippage_config: Optional[dict] = None):
        self.db_manager = db_manager
        self.live_trading = os.environ.get("ENABLE_TRADING", "false").lower() == "true"

        cfg = slippage_config or {}
        self.use_book_price = cfg.get("use_book_price", True)
        self.slippage_bps = cfg.get("slippage_bps", 50)

        mode = "LIVE" if self.live_trading else "SIMULATED"
        logger.info(
            f"OrderExecutor initialized: mode={mode}, "
            f"use_book_price={self.use_book_price}, slippage_bps={self.slippage_bps}"
        )

    def calc_execution_price(
        self,
        action: str,
        price: float,
        best_bid: Optional[float] = None,
        best_ask: Optional[float] = None,
    ) -> float:
        """約定価格を算出（スリッページ考慮）

        BUY: best_ask（なければ price）に正のスリッページを加算
        SELL: best_bid（なければ price）に負のスリッページを減算
        """
        base = price

        if self.use_book_price:
            if action == "BUY" and best_ask is not None:
                base = best_ask
            elif action == "SELL" and best_bid is not None:
                base = best_bid

        slip = self.slippage_bps / 10000
        if action == "BUY":
            exec_price = base * (1 + slip)
        else:
            exec_price = base * (1 - slip)

        return round(exec_price, 6)

    def execute(
        self,
        asset_id: str,
        market: Optional[str],
        action: str,
        price: float,
        amount_usdc: float,
        reason: str = "",
        best_bid: Optional[float] = None,
        best_ask: Optional[float] = None,
    ) -> Optional[int]:
        """注文を実行（シミュレーション）

        Args:
            best_bid: 最良買値（SELL時の基準価格）
            best_ask: 最良売値（BUY時の基準価格）

        Returns:
            Trade ID or None if failed
        """
        if self.live_trading:
            logger.warning("ライブ取引は未実装です。シミュレーションで実行します。")

        simulated = 0 if self.live_trading else 1
        exec_price = self.calc_execution_price(action, price, best_bid, best_ask)
        amount_usdc = round(amount_usdc, 6)

        trade_id = self.db_manager.save_trade(
            asset_id=asset_id,
            market=market,
            action=action,
            price=exec_price,
            amount_usdc=amount_usdc,
            simulated=simulated,
            reason=reason,
        )

        logger.info(
            f"[TRADE-SIM] {action} {amount_usdc:.2f} USDC @ {exec_price:.4f} "
            f"(raw={price:.4f}) | asset={asset_id[:16]}... | reason={reason}"
        )

        return trade_id, exec_price
