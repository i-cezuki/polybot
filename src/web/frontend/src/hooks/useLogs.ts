import { useQuery } from "@tanstack/react-query";
import { fetchLogs } from "../api/endpoints";
import { useUIStore } from "../store/uiStore";

export function useLogs(level?: string) {
  const pollingEnabled = useUIStore((s) => s.pollingEnabled);
  return useQuery({
    queryKey: ["logs", level],
    queryFn: () => fetchLogs(100, level),
    refetchInterval: pollingEnabled ? 2000 : false,
  });
}
