export interface StatusResponse {
  status: string;
  version: string;
  daily_pnl: number;
  total_assets_usdc: number;
  dry_run: boolean;
}

export interface DryRunRequest { enabled: boolean }
export interface DryRunResponse { dry_run: boolean; message: string }
export interface PanicCloseResponse { success: boolean; closed_positions: number; message: string }
export interface TestNotificationResponse { success: boolean; message: string }

export interface Position {
  asset_id: string;
  market: string;
  side: string;
  size_usdc: number;
  average_price: number;
  realized_pnl: number;
  opened_at: string | null;
  updated_at: string | null;
}

export interface PositionsResponse {
  positions: Position[];
  total_value_usdc: number;
}

export interface Trade {
  id?: number;
  asset_id: string;
  market?: string;
  action: string;
  price: number;
  amount_usdc: number;
  simulated?: number;
  realized_pnl: number;
  reason?: string;
  created_at?: string | null;
  timestamp?: string;
}

export interface TradesResponse {
  trades: Trade[];
  count: number;
}

export interface PerformanceResponse {
  total_pnl: number;
  win_rate: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  period_days: number;
}

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
}

export interface LogsResponse {
  logs: LogEntry[];
  count: number;
}

export interface EquityCurvePoint {
  timestamp: string;
  equity: number;
  capital: number;
}

export interface BacktestAnalysis {
  total_pnl: number;
  total_return_pct: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  avg_win: number;
  avg_loss: number;
  payoff_ratio: number;
  sharpe_ratio: number;
  max_drawdown_pct: number;
  initial_capital: number;
  final_capital: number;
}

export interface BacktestParams {
  days: number;
  market_id?: string;
  initial_capital: number;
}

export interface BacktestResponse {
  ticks_count: number;
  analysis: BacktestAnalysis;
  trades_count: number;
  equity_curve: EquityCurvePoint[];
  trades: Trade[];
  error?: string;
}
