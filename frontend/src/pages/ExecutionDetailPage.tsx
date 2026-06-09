import { useParams, useNavigate } from "react-router-dom";
import { useExecution, useExecutionReport } from "@/hooks/useExecutions";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  Accordion, AccordionContent, AccordionItem, AccordionTrigger,
} from "@/components/ui/accordion";
import { ArrowLeft, BarChart3, CheckCircle, Globe, Clock, FileText } from "lucide-react";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";
import type { CaseResult } from "@/types";

const triggerLabels: Record<string, string> = {
  manual: "手动", scheduled: "定时", webhook: "Webhook", api: "API",
};

export function ExecutionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: execution, isLoading, isError } = useExecution(id);
  const { data: report } = useExecutionReport(id);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
        <Skeleton className="h-[400px] w-full" />
      </div>
    );
  }

  if (isError || !execution) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive text-lg">加载执行详情失败</p>
        <Button variant="outline" className="mt-4" onClick={() => navigate("/executions")}>
          返回列表
        </Button>
      </div>
    );
  }

  const summary = execution.summary || { total_cases: 0, passed_cases: 0, failed_cases: 0, error_cases: 0 };
  const total = summary.total_cases || 0;
  const passRate = total > 0 ? ((summary.passed_cases / total) * 100).toFixed(1) : "0";
  const results: CaseResult[] = report?.results || execution.results || [];

  // Calculate timing stats
  const elapsedVals = results
    .map((r: CaseResult) => r.elapsed_ms)
    .filter((v: number) => v > 0);
  const avgElapsed =
    elapsedVals.length > 0
      ? (elapsedVals.reduce((a: number, b: number) => a + b, 0) / elapsedVals.length).toFixed(0)
      : "-";
  const sorted = [...elapsedVals].sort((a, b) => a - b);
  const p50 = sorted.length > 0 ? sorted[Math.floor(sorted.length * 0.5)] : "-";
  const p95 = sorted.length > 0 ? sorted[Math.floor(sorted.length * 0.95)] : "-";

  const formatDate = (d: string | null) => {
    if (!d) return "-";
    try {
      return format(new Date(d), "MM-dd HH:mm:ss", { locale: zhCN });
    } catch {
      return d;
    }
  };

  const caseStatusConfig: Record<string, { label: string; variant: "outline" | "default" | "destructive" | "secondary" }> = {
    PASS: { label: "通过", variant: "default" },
    FAIL: { label: "失败", variant: "destructive" },
    SKIP: { label: "跳过", variant: "secondary" },
    ERROR: { label: "错误", variant: "destructive" },
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/executions")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold">{execution.name || "执行详情"}</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            ID: {execution.id.slice(0, 8)}...
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              通过率
            </CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">{passRate}%</div>
            <p className="text-xs text-muted-foreground mt-1">
              {summary.passed_cases}/{total} 通过
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              总用例
            </CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{total}</div>
            <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
              <span className="flex items-center gap-1">
                <CheckCircle className="h-3 w-3 text-emerald-500" />
                {summary.passed_cases}
              </span>
              <span className="text-red-500">{summary.failed_cases} 失败</span>
              <span>{summary.error_cases} 错误</span>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              环境 / 触发
            </CardTitle>
            <Globe className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">{execution.env || "-"}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {triggerLabels[execution.trigger] || execution.trigger} 触发
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              状态
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <StatusBadge variant={execution.status.toLowerCase() as "passed" | "failed" | "running" | "pending" | "cancelled" | "error"} className="text-sm" />
            <p className="text-xs text-muted-foreground mt-2">
              {formatDate(execution.finished_at || execution.created_at)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Progress Bar */}
      <Card>
        <CardContent className="pt-4 pb-3">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">执行进度</span>
            <span className="text-sm text-muted-foreground">
              {summary.passed_cases}/{total} 通过 ({passRate}%)
            </span>
          </div>
          <Progress value={Number(passRate)} className="h-2.5" />
          <div className="flex items-center justify-between mt-2 text-xs text-muted-foreground">
            <span>通过 {summary.passed_cases}</span>
            <span>失败 {summary.failed_cases}</span>
            <span>错误 {summary.error_cases}</span>
          </div>
        </CardContent>
      </Card>

      {/* Case Results */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">用例结果 ({total})</CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm">
                仅看失败
              </Button>
              <Button variant="outline" size="sm">
                展开全部
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {results.length > 0 ? (
            <Accordion type="multiple" className="space-y-2">
              {results.map((r: CaseResult) => {
                const cfg = caseStatusConfig[r.status] || caseStatusConfig.ERROR;
                return (
                  <AccordionItem
                    key={r.case_id}
                    value={r.case_id}
                    className="border rounded-lg px-4"
                  >
                    <AccordionTrigger className="hover:no-underline py-3">
                      <div className="flex items-center gap-3 flex-1 pr-4">
                        <Badge variant={cfg.variant} className="shrink-0">
                          {cfg.label}
                        </Badge>
                        <span className="font-medium text-sm">{r.case_name}</span>
                        <span className="text-xs text-muted-foreground ml-auto">
                          {r.elapsed_ms > 0 ? `${r.elapsed_ms}ms` : "-"}
                        </span>
                      </div>
                    </AccordionTrigger>
                    <AccordionContent className="pb-3">
                      <div className="rounded-md bg-muted/50 p-3 space-y-2 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">状态:</span>
                          <Badge variant={cfg.variant}>{cfg.label}</Badge>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">耗时:</span>
                          <span>{r.elapsed_ms > 0 ? `${r.elapsed_ms}ms` : "-"}</span>
                        </div>
                        {r.error && (
                          <div>
                            <span className="text-muted-foreground">错误信息:</span>
                            <pre className="mt-1 rounded bg-destructive/10 p-2 text-xs text-destructive whitespace-pre-wrap font-mono">
                              {r.error}
                            </pre>
                          </div>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                );
              })}
            </Accordion>
          ) : (
            <div className="py-8 text-center text-muted-foreground">
              暂未生成用例结果数据
            </div>
          )}
        </CardContent>
      </Card>

      {/* Timing Stats */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">耗时统计</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-4 gap-6 text-center">
            <div>
              <p className="text-2xl font-bold">{avgElapsed}ms</p>
              <p className="text-xs text-muted-foreground">平均</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{p50}ms</p>
              <p className="text-xs text-muted-foreground">P50</p>
            </div>
            <div>
              <p className="text-2xl font-bold">{p95}ms</p>
              <p className="text-xs text-muted-foreground">P95</p>
            </div>
            <div>
              <p className="text-2xl font-bold">
                {sorted.length > 0 ? sorted[sorted.length - 1] : "-"}ms
              </p>
              <p className="text-xs text-muted-foreground">最大值</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
