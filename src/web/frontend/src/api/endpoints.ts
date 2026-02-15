import { apiFetch } from "./client";
import type {
  StatusResponse,
  PositionsResponse,
  TradesResponse,
  PerformanceResponse,
  LogsResponse,
  BacktestParams,
  BacktestResponse,
} from "../types/api";

export function fetchStatus(): Promise<StatusResponse> {
  return apiFetch<StatusResponse>("/api/status");
}

export function fetchPositions(): Promise<PositionsResponse> {
  return apiFetch<PositionsResponse>("/api/positions");
}

export function fetchTrades(
  limit = 100,
  sinceHours = 24
): Promise<TradesResponse> {
  return apiFetch<TradesResponse>(
    `/api/trades?limit=${limit}&since_hours=${sinceHours}`
  );
}

export function fetchPerformance(days = 7): Promise<PerformanceResponse> {
  return apiFetch<PerformanceResponse>(`/api/performance?days=${days}`);
}

export function fetchLogs(
  limit = 100,
  level?: string
): Promise<LogsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (level) params.set("level", level);
  return apiFetch<LogsResponse>(`/api/logs?${params}`);
}

export function runBacktest(
  params: BacktestParams
): Promise<BacktestResponse> {
  const query = new URLSearchParams({
    days: String(params.days),
    initial_capital: String(params.initial_capital),
  });
  if (params.market_id) query.set("market_id", params.market_id);
  return apiFetch<BacktestResponse>(`/api/backtest?${query}`, {
    method: "POST",
  });
}
