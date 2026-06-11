import { create } from "zustand";

export interface AuthUser {
  id: string;
  username: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

interface AuthState {
  token: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuth: (token: string, refreshToken: string, user: AuthUser) => void;
  setToken: (token: string) => void;
  setUser: (user: AuthUser) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
}

const TOKEN_KEY = "autotest-token";
const REFRESH_TOKEN_KEY = "autotest-refresh-token";
const USER_KEY = "autotest-user";

function loadPersistedAuth(): { token: string | null; refreshToken: string | null; user: AuthUser | null } {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    const userStr = localStorage.getItem(USER_KEY);
    const user = userStr ? JSON.parse(userStr) : null;
    return { token, refreshToken, user };
  } catch {
    return { token: null, refreshToken: null, user: null };
  }
}

const persisted = loadPersistedAuth();

export const useAuthStore = create<AuthState>((set) => ({
  token: persisted.token,
  refreshToken: persisted.refreshToken,
  user: persisted.user,
  isAuthenticated: !!(persisted.token && persisted.user),
  isLoading: false,

  setAuth: (token, refreshToken, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ token, refreshToken, user, isAuthenticated: true });
  },

  setToken: (token) => {
    localStorage.setItem(TOKEN_KEY, token);
    set({ token, isAuthenticated: !!(token && useAuthStore.getState().user) });
  },

  setUser: (user) => {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ user });
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({ token: null, refreshToken: null, user: null, isAuthenticated: false });
  },

  setLoading: (isLoading) => set({ isLoading }),
}));
