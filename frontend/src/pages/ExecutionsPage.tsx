import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useExecutions } from "@/hooks/useExecutions";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { ExternalLink } from "lucide-react";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";

const statusConfig: Record<
  string,
  { label: string; variant: "default" | "success" | "destructive" | "warning" | "secondary" }
> = {
  pending: { label: "等待中", variant: "secondary" },
  running: { label: "运行中", variant: "default" },
  passed: { label: "通过", variant: "success" },
  failed: { label: "失败", variant: "destructive" },
  cancelled: { label: "已取消", variant: "warning" },
};

const triggerLabels: Record<string, string> = {
  manual: "手动",
  scheduled: "定时",
  ci: "CI",
};

export function ExecutionsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const page = Number(searchParams.get("page") || "1");
  const status = searchParams.get("status") || "all";

  const { data, isLoading, isError } = useExecutions({
    page,
    page_size: 15,
    status: status !== "all" ? status : undefined,
  });

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    try {
      return format(new Date(dateStr), "MM-dd HH:mm:ss", { locale: zhCN });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">执行历史</h1>
      </div>

      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <Select
              value={status}
              onValueChange={(v) =>
                setSearchParams((prev) => {
                  const next = new URLSearchParams(prev);
                  if (v === "all") next.delete("status");
                  else next.set("status", v);
                  next.set("page", "1");
                  return next;
                })
              }
            >
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="状态筛选" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">全部状态</SelectItem>
                <SelectItem value="passed">通过</SelectItem>
                <SelectItem value="failed">失败</SelectItem>
                <SelectItem value="running">运行中</SelectItem>
                <SelectItem value="pending">等待中</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="p-6 text-center text-destructive">
              加载失败，请检查后端服务。
            </div>
          ) : data && data.items.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[380px]">执行 ID</TableHead>
                    <TableHead>套件名称</TableHead>
                    <TableHead className="w-[80px]">状态</TableHead>
                    <TableHead className="w-[80px]">触发方式</TableHead>
                    <TableHead className="w-[150px]">开始时间</TableHead>
                    <TableHead className="w-[150px]">结束时间</TableHead>
                    <TableHead className="w-[80px]">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((ex) => {
                    const cfg = statusConfig[ex.status] || statusConfig.pending;
                    return (
                      <TableRow
                        key={ex.id}
                        className="cursor-pointer"
                        onClick={() => navigate(`/executions/${ex.id}`)}
                      >
                        <TableCell className="font-mono text-xs">
                          {ex.id.slice(0, 12)}...
                        </TableCell>
                        <TableCell>{ex.suite_name}</TableCell>
                        <TableCell>
                          <Badge variant={cfg.variant}>{cfg.label}</Badge>
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {triggerLabels[ex.trigger] || ex.trigger}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(ex.started_at)}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {formatDate(ex.finished_at)}
                        </TableCell>
                        <TableCell>
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
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>

              <div className="flex items-center justify-between p-4 border-t">
                <span className="text-sm text-muted-foreground">
                  共 {data.pagination.total} 条，第 {data.pagination.page}/{data.pagination.total_pages} 页
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() =>
                      setSearchParams((prev) => {
                        const next = new URLSearchParams(prev);
                        next.set("page", String(page - 1));
                        return next;
                      })
                    }
                  >
                    上一页
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= data.pagination.total_pages}
                    onClick={() =>
                      setSearchParams((prev) => {
                        const next = new URLSearchParams(prev);
                        next.set("page", String(page + 1));
                        return next;
                      })
                    }
                  >
                    下一页
                  </Button>
                </div>
              </div>
            </>
          ) : (
            <div className="p-12 text-center text-muted-foreground">
              暂无执行记录。
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
