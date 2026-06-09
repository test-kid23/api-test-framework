import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";
import { Loader2 } from "lucide-react";

const statusBadgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        // 执行状态
        passed: "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
        failed: "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300",
        running: "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300",
        pending: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-300",
        cancelled: "border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400",
        error: "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300",

        // 优先级
        P0: "border-red-200 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300",
        P1: "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-300",
        P2: "border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300",
        P3: "border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-400",

        // 通用
        success: "border-emerald-200 bg-emerald-50 text-emerald-700",
        warning: "border-amber-200 bg-amber-50 text-amber-700",
        info: "border-blue-200 bg-blue-50 text-blue-700",
        destructive: "border-red-200 bg-red-50 text-red-700",
      },
    },
    defaultVariants: {
      variant: "info",
    },
  }
);

const statusLabels: Record<string, string> = {
  passed: "通过",
  failed: "失败",
  running: "运行中",
  pending: "等待中",
  cancelled: "已取消",
  error: "错误",
  P0: "P0",
  P1: "P1",
  P2: "P2",
  P3: "P3",
  success: "成功",
  warning: "警告",
  info: "信息",
  destructive: "危险",
};

export interface StatusBadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusBadgeVariants> {
  loading?: boolean;
}

export function StatusBadge({
  className,
  variant,
  loading,
  children,
  ...props
}: StatusBadgeProps) {
  const label = children ?? (variant ? statusLabels[variant] ?? variant : "");

  return (
    <span
      className={cn(statusBadgeVariants({ variant }), className)}
      {...props}
    >
      {loading && <Loader2 className="h-3 w-3 animate-spin" />}
      {label}
    </span>
  );
}

export { statusBadgeVariants };
