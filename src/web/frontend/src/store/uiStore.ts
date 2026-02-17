import { create } from "zustand";

interface UIState {
  pollingEnabled: boolean;
  sidebarOpen: boolean;
  dryRunOverride: boolean | null;
  togglePolling: () => void;
  setSidebarOpen: (open: boolean) => void;
  setDryRunOverride: (value: boolean | null) => void;
}

export const useUIStore = create<UIState>((set) => ({
  pollingEnabled: true,
  sidebarOpen: false,
  dryRunOverride: null,
  togglePolling: () => set((s) => ({ pollingEnabled: !s.pollingEnabled })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setDryRunOverride: (value) => set({ dryRunOverride: value }),
}));
