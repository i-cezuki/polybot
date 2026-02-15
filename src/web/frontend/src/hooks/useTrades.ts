import { useQuery } from "@tanstack/react-query";
import { fetchTrades } from "../api/endpoints";
import { useUIStore } from "../store/uiStore";

export function useTrades() {
  const pollingEnabled = useUIStore((s) => s.pollingEnabled);
  return useQuery({
    queryKey: ["trades"],
    queryFn: () => fetchTrades(),
    refetchInterval: pollingEnabled ? 30000 : false,
  });
}
