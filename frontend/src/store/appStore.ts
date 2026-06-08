import { create } from "zustand";

interface AppState {
  currentUser: { name: string; role: string };
  selectedEnv: string;
  sidebarOpen: boolean;
  setSelectedEnv: (env: string) => void;
  toggleSidebar: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  currentUser: {
    name: "管理员",
    role: "admin",
  },
  selectedEnv: "dev",
  sidebarOpen: true,
  setSelectedEnv: (env) => set({ selectedEnv: env }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
