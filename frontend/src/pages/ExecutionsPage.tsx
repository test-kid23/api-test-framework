import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useExecutions, useTriggerExecution } from "@/hooks/useExecutions";
import { useSuites } from "@/hooks/useSuites";
import { useEnvironments } from "@/hooks/useEnvironments";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { StatusBadge } from "@/components/ui/status-badge";
import { EmptyState } from "@/components/ui/empty-state";
import { toast } from "sonner";
import { Play, X, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";
import type { Execution, ExecutionTrigger } from "@/types";
import { usePermission } from "@/hooks/usePermission";

const triggerLabels: Record<ExecutionTrigger, string> = {
  manual: "手动", scheduled: "定时", webhook: "Webhook", api: "API",
};

export function ExecutionsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { canEdit } = usePermission();

  const page = Number(searchParams.get("page") || "1");
  const statusFilter = searchParams.get("status") || "all";

  const [triggerOpen, setTriggerOpen] = useState(false);
  const [triggerEnv, setTriggerEnv] = useState("");
  const [triggerSuiteId, setTriggerSuiteId] = useState("");

  const { data, isLoading, isError, isFetching } = useExecutions({
    page,
    page_size: 15,
    status: statusFilter !== "all" ? statusFilter : undefined,
  });
  const { data: suitesData } = useSuites({ page_size: 100 });
  const { data: envsData } = useEnvironments({ page_size: 20 });
  const triggerMutation = useTriggerExecution();

  const suites = suitesData?.items || [];
  const envs = envsData?.items || [];

  const handleTrigger = async () => {
    if (!triggerEnv) {
      toast.error("请选择目标环境");
      return;
    }
    try {
      await triggerMutation.mutateAsync({
        case_ids: [],
        suite_id: triggerSuiteId || undefined,
        env: triggerEnv,
        trigger: "manual",
      });
      toast.success("执行已触发");
      setTriggerOpen(false);
    } catch {
      toast.error("触发执行失败");
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    try {
      return format(new Date(dateStr), "MM-dd HH:mm:ss", { locale: zhCN });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">执行历史</h1>
          {isFetching && !isLoading && (
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <RefreshCw className="h-3 w-3 animate-spin" />
              自动刷新中
            </span>
          )}
        </div>
        {canEdit && (
        <Button onClick={() => setTriggerOpen(true)} className="gap-2">
          <Play className="h-4 w-4" />
          触发新执行
        </Button>
        )}
      </div>

      {/* Status Tabs */}
      <div className="flex gap-1 bg-muted rounded-lg p-1 w-fit">
        {["all", "PASSED", "FAILED", "RUNNING", "PENDING"].map((s) => {
          const labelMap: Record<string, string> = {
            all: "全部", PASSED: "通过", FAILED: "失败", RUNNING: "运行中", PENDING: "等待中",
          };
          return (
            <Button
              key={s}
              variant={statusFilter === s ? "default" : "ghost"}
              size="sm"
              onClick={() =>
                setSearchParams((prev) => {
                  const n = new URLSearchParams(prev);
                  if (s === "all") n.delete("status");
                  else n.set("status", s);
                  n.set("page", "1");
                  return n;
                })
              }
            >
              {labelMap[s]}
            </Button>
          );
        })}
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-0">
              <div className="flex items-center gap-4 pb-3 border-b">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-24 ml-auto" />
                <Skeleton className="h-4 w-12" />
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-28" />
                <Skeleton className="h-4 w-16" />
              </div>
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 py-3 border-b last:border-0">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-5 w-14 rounded-full" />
                  <div className="flex items-center gap-2 ml-auto">
                    <Skeleton className="h-4 w-8" />
                    <Skeleton className="h-4 w-4" />
                    <Skeleton className="h-4 w-8" />
                  </div>
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-8 w-8 rounded" />
                </div>
              ))}
            </div>
          ) : isError ? (
            <div className="p-12 text-center text-destructive">
              加载失败，请检查后端服务。
            </div>
          ) : data && data.items.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>执行名称</TableHead>
                    <TableHead className="w-[90px]">状态</TableHead>
                    <TableHead className="w-[110px]">通过/失败</TableHead>
                    <TableHead className="w-[70px]">触发</TableHead>
                    <TableHead className="w-[130px]">开始时间</TableHead>
                    <TableHead className="w-[130px]">结束时间</TableHead>
                    <TableHead className="w-[80px]">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((ex: Execution) => {
                    const summary = ex.summary;
                    const isRunning = ex.status === "RUNNING";
                    const progress =
                      summary && summary.total_cases > 0
                        ? ((summary.passed_cases + summary.failed_cases + summary.error_cases) /
                            summary.total_cases) *
                          100
                        : 0;

                    return (
                      <TableRow
                        key={ex.id}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => navigate(`/executions/${ex.id}`)}
                      >
                        <TableCell>
                          <div>
                            <p className="font-medium">{ex.name || "未命名执行"}</p>
                            {isRunning && (
                              <Progress value={progress} className="h-1.5 mt-1.5" />
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          <StatusBadge variant={ex.status.toLowerCase() as "passed" | "failed" | "running" | "pending" | "cancelled" | "error"} />
                        </TableCell>
                        <TableCell className="text-sm">
                          {summary ? (
                            <div className="flex items-center gap-2">
                              <span className="text-emerald-600 font-medium">
                                {summary.passed_cases}
                              </span>
                              <span className="text-muted-foreground">/</span>
                              <span className="text-red-500 font-medium">
                                {summary.failed_cases}
                              </span>
                              <span className="text-muted-foreground text-xs ml-1">
                                (共{summary.total_cases})
                              </span>
                            </div>
                          ) : (
                            "-"
                          )}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {triggerLabels[ex.trigger] || ex.trigger}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground font-mono">
                          {formatDate(ex.started_at)}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground font-mono">
                          {formatDate(ex.finished_at)}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/executions/${ex.id}`);
                              }}
                            >
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                            {isRunning && (
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  // cancel execution
                                }}
                              >
                                <X className="h-4 w-4 text-destructive" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>

              {/* Pagination */}
              <div className="flex items-center justify-between px-4 py-3 border-t">
                <span className="text-sm text-muted-foreground">
                  共 {data.pagination.total} 条
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() =>
                      setSearchParams((prev) => {
                        const n = new URLSearchParams(prev);
                        n.set("page", String(page - 1));
                        return n;
                      })
                    }
                  >
                    上一页
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= (data.pagination.total_pages || 1)}
                    onClick={() =>
                      setSearchParams((prev) => {
                        const n = new URLSearchParams(prev);
                        n.set("page", String(page + 1));
                        return n;
                      })
                    }
                  >
                    下一页
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <div className="p-12">
              <EmptyState
                icon={Play}
                title="暂无执行记录"
                description="选择套件和目标环境，触发一次新的测试执行"
                action={{ label: "触发新执行", onClick: () => setTriggerOpen(true) }}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Trigger Dialog */}
      <Dialog open={triggerOpen} onOpenChange={setTriggerOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>触发新执行</DialogTitle>
            <DialogDescription>
              选择套件和目标环境，触发一次新的测试执行。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>目标环境 *</Label>
              <Select value={triggerEnv} onValueChange={setTriggerEnv}>
                <SelectTrigger>
                  <SelectValue placeholder="选择环境..." />
                </SelectTrigger>
                <SelectContent>
                  {envs.map((env: { id: string; name: string }) => (
                    <SelectItem key={env.id} value={env.name}>
                      {env.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>关联套件（可选）</Label>
              <Select value={triggerSuiteId} onValueChange={setTriggerSuiteId}>
                <SelectTrigger>
                  <SelectValue placeholder="选择套件或留空..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">不使用套件</SelectItem>
                  {suites.map((s: { id: string; name: string }) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTriggerOpen(false)}>
              取消
            </Button>
            <Button onClick={handleTrigger} disabled={triggerMutation.isPending}>
              {triggerMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              开始执行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
