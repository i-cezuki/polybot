import { useMutation, useQueryClient } from "@tanstack/react-query";
import { panicClose } from "../api/endpoints";

export function usePanicClose() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => panicClose(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["status"] });
      queryClient.invalidateQueries({ queryKey: ["positions"] });
      queryClient.invalidateQueries({ queryKey: ["trades"] });
    },
  });
}
