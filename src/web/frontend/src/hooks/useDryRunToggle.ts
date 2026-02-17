import { useMutation, useQueryClient } from "@tanstack/react-query";
import { setDryRun } from "../api/endpoints";
import { useUIStore } from "../store/uiStore";
import type { DryRunRequest } from "../types/api";

export function useDryRunToggle() {
  const queryClient = useQueryClient();
  const setDryRunOverride = useUIStore((s) => s.setDryRunOverride);

  return useMutation({
    mutationFn: (params: DryRunRequest) => setDryRun(params),
    onMutate: (params) => {
      setDryRunOverride(params.enabled);
    },
    onSuccess: () => {
      setDryRunOverride(null);
      queryClient.invalidateQueries({ queryKey: ["status"] });
    },
    onError: () => {
      setDryRunOverride(null);
    },
  });
}
