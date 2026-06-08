import { useParams, useNavigate } from "react-router-dom";
import { useExecution } from "@/hooks/useExecutions";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowLeft, Clock, CheckCircle, XCircle, BarChart3 } from "lucide-react";

const statusConfig: Record<
  string,
  { label: string; variant: "default" | "success" | "destructive" | "warning" | "secondary" }
> = {
  passed: { label: "通过", variant: "success" },
  failed: { label: "失败", variant: "destructive" },
  error: { label: "错误", variant: "destructive" },
  skipped: { label: "跳过", variant: "secondary" },
};

export function ExecutionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: execution, isLoading, isError } = useExecution(id);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-4 gap-4">
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

  const passRate =
    execution.total_cases > 0
      ? ((execution.passed_cases / execution.total_cases) * 100).toFixed(1)
      : "0";

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate("/executions")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-2xl font-bold">执行详情</h1>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              通过率
            </CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{passRate}%</div>
            <p className="text-xs text-muted-foreground">
              {execution.passed_cases}/{execution.total_cases} 通过
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              总用例数
            </CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{execution.total_cases}</div>
            <p className="text-xs text-muted-foreground">
              失败 {execution.failed_cases} 个
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              环境
            </CardTitle>
            <XCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{execution.env_name}</div>
            <p className="text-xs text-muted-foreground capitalize">
              {execution.trigger} 触发
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              状态
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <Badge
              variant={
                execution.status === "passed"
                  ? "success"
                  : execution.status === "failed"
                  ? "destructive"
                  : "default"
              }
            >
              {execution.status === "passed"
                ? "通过"
                : execution.status === "failed"
                ? "失败"
                : execution.status}
            </Badge>
          </CardContent>
        </Card>
      </div>

      {/* Case Results Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">用例结果</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {execution.case_results && execution.case_results.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>用例名称</TableHead>
                  <TableHead className="w-[80px]">状态</TableHead>
                  <TableHead className="w-[100px]">耗时</TableHead>
                  <TableHead>错误信息</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {execution.case_results.map((cr) => {
                  const cfg = statusConfig[cr.status] || statusConfig.error;
                  return (
                    <TableRow key={cr.case_id}>
                      <TableCell className="font-medium">
                        {cr.case_name}
                      </TableCell>
                      <TableCell>
                        <Badge variant={cfg.variant}>{cfg.label}</Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {cr.elapsed_ms}ms
                      </TableCell>
                      <TableCell className="text-sm text-destructive max-w-[300px] truncate">
                        {cr.error_message || "-"}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-muted-foreground">
              暂无用例结果数据。
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
