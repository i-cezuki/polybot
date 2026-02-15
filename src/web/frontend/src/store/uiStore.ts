import { create } from "zustand";

interface UIState {
  pollingEnabled: boolean;
  sidebarOpen: boolean;
  togglePolling: () => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  pollingEnabled: true,
  sidebarOpen: false,
  togglePolling: () => set((s) => ({ pollingEnabled: !s.pollingEnabled })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));
