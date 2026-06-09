import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/store/authStore";

interface RoleGuardProps {
  roles: string[];
  children: React.ReactNode;
  /** 无权限时跳转路径，默认 /cases */
  fallback?: string;
}

/**
 * 路由级权限守卫：检查当前用户角色是否在允许列表中。
 * 不通过则重定向到 fallback（默认 /cases）。
 */
export function RoleGuard({ roles, children, fallback = "/cases" }: RoleGuardProps) {
  const user = useAuthStore((s) => s.user);
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (!roles.includes(user.role)) {
    return <Navigate to={fallback} replace />;
  }
  return <>{children}</>;
}
