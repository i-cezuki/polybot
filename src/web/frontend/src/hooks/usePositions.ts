import { useQuery } from "@tanstack/react-query";
import { fetchPositions } from "../api/endpoints";
import { useUIStore } from "../store/uiStore";

export function usePositions() {
  const pollingEnabled = useUIStore((s) => s.pollingEnabled);
  return useQuery({
    queryKey: ["positions"],
    queryFn: fetchPositions,
    refetchInterval: pollingEnabled ? 10000 : false,
  });
}
