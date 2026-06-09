import { useAuthStore } from "@/store/authStore";

export interface Permission {
  /** 是否超级管理员 */
  isAdmin: boolean;
  /** 是否编辑者 */
  isEditor: boolean;
  /** 是否观察者（只读） */
  isViewer: boolean;
  /** 是否可编辑/创建 */
  canEdit: boolean;
  /** 是否可删除 */
  canDelete: boolean;
}

export function usePermission(): Permission {
  const user = useAuthStore((s) => s.user);
  const role = user?.role || "viewer";

  return {
    isAdmin: role === "admin",
    isEditor: role === "editor",
    isViewer: role === "viewer",
    canEdit: role === "admin" || role === "editor",
    canDelete: role === "admin",
  };
}
