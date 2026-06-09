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
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setAuth: (token: string, user: AuthUser) => void;
  setUser: (user: AuthUser) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
}

const TOKEN_KEY = "autotest-token";
const USER_KEY = "autotest-user";

function loadPersistedAuth(): { token: string | null; user: AuthUser | null } {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    const userStr = localStorage.getItem(USER_KEY);
    const user = userStr ? JSON.parse(userStr) : null;
    return { token, user };
  } catch {
    return { token: null, user: null };
  }
}

const persisted = loadPersistedAuth();

export const useAuthStore = create<AuthState>((set) => ({
  token: persisted.token,
  user: persisted.user,
  isAuthenticated: !!(persisted.token && persisted.user),
  isLoading: false,

  setAuth: (token, user) => {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ token, user, isAuthenticated: true });
  },

  setUser: (user) => {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
    set({ user });
  },

  logout: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    set({ token: null, user: null, isAuthenticated: false });
  },

  setLoading: (isLoading) => set({ isLoading }),
}));
