import { useQuery } from "@tanstack/react-query";
import { fetchPerformance } from "../api/endpoints";
import { useUIStore } from "../store/uiStore";

export function usePerformance() {
  const pollingEnabled = useUIStore((s) => s.pollingEnabled);
  return useQuery({
    queryKey: ["performance"],
    queryFn: () => fetchPerformance(),
    refetchInterval: pollingEnabled ? 30000 : false,
  });
}
