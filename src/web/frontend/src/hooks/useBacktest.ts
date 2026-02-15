import { useMutation } from "@tanstack/react-query";
import { runBacktest } from "../api/endpoints";
import type { BacktestParams } from "../types/api";

export function useBacktest() {
  return useMutation({
    mutationFn: (params: BacktestParams) => runBacktest(params),
  });
}
