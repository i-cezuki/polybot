import { useMutation } from "@tanstack/react-query";
import { testNotification } from "../api/endpoints";

export function useTestNotification() {
  return useMutation({
    mutationFn: () => testNotification(),
  });
}
