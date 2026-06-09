import { create } from "zustand";

type Theme = "light" | "dark" | "system";

interface AppState {
  currentUser: { name: string; role: string };
  selectedEnv: string;
  sidebarOpen: boolean;
  theme: Theme;
  mobileSidebarOpen: boolean;
  setSelectedEnv: (env: string) => void;
  toggleSidebar: () => void;
  setTheme: (theme: Theme) => void;
  toggleMobileSidebar: () => void;
}

function getInitialTheme(): Theme {
  const stored = localStorage.getItem("autotest-theme") as Theme | null;
  if (stored === "light" || stored === "dark" || stored === "system") return stored;
  return "system";
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.remove("light", "dark");
  if (theme === "system") {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.classList.add(prefersDark ? "dark" : "light");
  } else {
    root.classList.add(theme);
  }
}

// Apply on load
applyTheme(getInitialTheme());

export const useAppStore = create<AppState>((set) => ({
  currentUser: {
    name: "管理员",
    role: "admin",
  },
  selectedEnv: "dev",
  sidebarOpen: true,
  theme: getInitialTheme(),
  mobileSidebarOpen: false,
  setSelectedEnv: (env) => set({ selectedEnv: env }),
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  setTheme: (theme) => {
    localStorage.setItem("autotest-theme", theme);
    applyTheme(theme);
    set({ theme });
  },
  toggleMobileSidebar: () => set((s) => ({ mobileSidebarOpen: !s.mobileSidebarOpen })),
}));

// Listen for system theme changes
if (typeof window !== "undefined") {
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    const state = useAppStore.getState();
    if (state.theme === "system") {
      applyTheme("system");
    }
  });
}
