import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";
import { getMe } from "@/api/auth";
import { Loader2 } from "lucide-react";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { token, isAuthenticated, setAuth, logout, setLoading } = useAuthStore();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function verify() {
      if (!token) {
        setChecking(false);
        return;
      }

      setLoading(true);
      try {
        const user = await getMe();
        if (!cancelled) {
          setAuth(token, user);
        }
      } catch {
        // Token 无效 — 清除状态
        if (!cancelled) {
          logout();
        }
      } finally {
        if (!cancelled) {
          setChecking(false);
        }
      }
    }

    verify();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/40">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">验证登录状态...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
