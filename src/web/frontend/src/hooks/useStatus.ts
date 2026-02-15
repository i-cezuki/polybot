import { useQuery } from "@tanstack/react-query";
import { fetchStatus } from "../api/endpoints";
import { useUIStore } from "../store/uiStore";

export function useStatus() {
  const pollingEnabled = useUIStore((s) => s.pollingEnabled);
  return useQuery({
    queryKey: ["status"],
    queryFn: fetchStatus,
    refetchInterval: pollingEnabled ? 5000 : false,
  });
}
