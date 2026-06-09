import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/api/reports";
import type { ExecutionStatus } from "@/types";

export function ReportsPage() {
  const navigate = useNavigate();
  const [envFilter, setEnvFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["reports", { env_name: envFilter || undefined }],
    queryFn: () => reportsApi.list({ page: 1, page_size: 100, env_name: envFilter || undefined }),
  });

  const reports = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">报告列表</h1>
        <Select value={envFilter} onValueChange={setEnvFilter}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="全部环境" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">全部环境</SelectItem>
            <SelectItem value="dev">开发环境</SelectItem>
            <SelectItem value="test">测试环境</SelectItem>
            <SelectItem value="staging">预发布</SelectItem>
            <SelectItem value="prod">生产环境</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-0">
              <div className="flex items-center gap-4 pb-3 border-b">
                <Skeleton className="h-4 w-36" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-14 ml-auto" />
                <Skeleton className="h-4 w-10" />
                <Skeleton className="h-4 w-10" />
                <Skeleton className="h-4 w-10" />
                <Skeleton className="h-4 w-24" />
              </div>
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 py-3 border-b last:border-0">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-5 w-14 rounded-full" />
                  <Skeleton className="h-5 w-14 rounded-full" />
                  <Skeleton className="h-4 w-12 ml-auto font-mono" />
                  <Skeleton className="h-4 w-8" />
                  <Skeleton className="h-4 w-8" />
                  <Skeleton className="h-4 w-8" />
                  <Skeleton className="h-4 w-28" />
                </div>
              ))}
            </div>
          ) : reports.length === 0 ? (
            <div className="py-0">
              <EmptyState
                icon={FileText}
                title={envFilter ? "该环境下暂无报告" : "暂无报告数据"}
                description="执行测试后将自动生成报告"
              />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>执行名称</TableHead>
                  <TableHead>环境</TableHead>
                  <TableHead>状态</TableHead>
                  <TableHead className="text-right">通过率</TableHead>
                  <TableHead className="text-right">总数</TableHead>
                  <TableHead className="text-right">通过</TableHead>
                  <TableHead className="text-right">失败</TableHead>
                  <TableHead>生成时间</TableHead>
                  <TableHead className="w-[60px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((r) => (
                  <TableRow
                    key={r.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => navigate(`/executions/${r.execution_id}`)}
                  >
                    <TableCell className="font-medium">{r.execution_name || r.id}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {r.env || "—"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <StatusBadge
                        variant={
                          (r.status?.toLowerCase() || "pending") as
                            | "passed" | "failed" | "running" | "pending" | "cancelled" | "error"
                        }
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <span
                        className={`font-medium ${
                          r.pass_rate >= 90
                            ? "text-emerald-600"
                            : r.pass_rate >= 70
                            ? "text-amber-600"
                            : "text-red-600"
                        }`}
                      >
                        {r.pass_rate.toFixed(1)}%
                      </span>
                    </TableCell>
                    <TableCell className="text-right text-sm">{r.total_cases}</TableCell>
                    <TableCell className="text-right text-sm text-emerald-600">
                      {r.passed}
                    </TableCell>
                    <TableCell className="text-right text-sm text-red-600">
                      {r.failed}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {r.created_at ? new Date(r.created_at).toLocaleString("zh-CN") : "—"}
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          navigate(`/executions/${r.execution_id}`);
                        }}
                      >
                        <ExternalLink className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
