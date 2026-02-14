"""
取引戦略テンプレート（AI Co-Pilot Guide 準拠）

calculate_signal(data) を編集して取引ロジックを定義してください。

data dict:
    price         : float  - 現在価格
    market_id     : str    - マーケットID
    history       : list   - 直近の価格履歴 [{price, timestamp}, ...]
    position_usdc : float  - 現在のポジションサイズ (USDC)
    side          : str    - ポジション方向 ("BUY" or None)
    best_bid      : float  - 最良買値
    best_ask      : float  - 最良売値
    timestamp     : str    - イベントタイムスタンプ

戻り値 dict:
    action : str   - "BUY", "SELL", "HOLD"
    amount : float - 取引量 (USDC)
    reason : str   - 取引理由
"""


def calculate_signal(data: dict) -> dict:
    """閾値ベースの単純戦略（デフォルト）"""
    price = data.get("price")
    position_usdc = data.get("position_usdc", 0.0)

    if price is None:
        return {"action": "HOLD", "amount": 0, "reason": "価格データなし"}

    # 安い → 買い
    if price < 0.30 and position_usdc == 0.0:
        return {
            "action": "BUY",
            "amount": 10.0,
            "reason": f"価格 {price:.4f} < 0.30 閾値で買い",
        }

    # 高い → 売り（ポジションがある場合のみ）
    if price > 0.70 and position_usdc > 0.0:
        return {
            "action": "SELL",
            "amount": position_usdc,
            "reason": f"価格 {price:.4f} > 0.70 閾値で売り",
        }

    return {"action": "HOLD", "amount": 0, "reason": "条件未達"}
