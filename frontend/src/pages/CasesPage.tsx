import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useCases, useDeleteCase } from "@/hooks/useCases";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  CommandDialog, CommandEmpty, CommandGroup,
  CommandInput, CommandItem, CommandList,
} from "@/components/ui/command";
import {
  Pagination, PaginationContent, PaginationItem,
  PaginationLink, PaginationNext, PaginationPrevious,
} from "@/components/ui/pagination";
import { toast } from "sonner";
import { Plus, Search, Pencil, Trash2, Loader2, Upload, XSquare, FileText } from "lucide-react";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";
import type { TestCase, CasePriority } from "@/types";
import { usePermission } from "@/hooks/usePermission";

const PRIORITIES: CasePriority[] = ["P0", "P1", "P2", "P3"];
const priorityColors: Record<CasePriority, "destructive" | "default" | "secondary" | "outline"> = {
  P0: "destructive", P1: "default", P2: "secondary", P3: "outline",
};

export function CasesPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { canEdit } = usePermission();

  const page = Number(searchParams.get("page") || "1");
  const search = searchParams.get("search") || "";
  const priority = searchParams.get("priority") || "all";

  const [searchInput, setSearchInput] = useState(search);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleteOpen, setBatchDeleteOpen] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);

  const { data, isLoading, isError } = useCases({
    page,
    page_size: 15,
    search: search || undefined,
    priority: priority !== "all" ? priority : undefined,
  });
  const deleteCase = useDeleteCase();

  // Close selection when data changes
  useEffect(() => {
    setSelectedIds(new Set());
  }, [data?.items]);

  // ⌘K keyboard shortcut
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setCmdOpen((v) => !v);
      }
    };
    document.addEventListener("keydown", down);
    return () => document.removeEventListener("keydown", down);
  }, []);

  const handleSearch = () => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (searchInput) next.set("search", searchInput);
      else next.delete("search");
      next.set("page", "1");
      return next;
    });
  };

  const goToPage = useCallback(
    (p: number) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set("page", String(p));
        return next;
      });
    },
    [setSearchParams]
  );

  const toggleSelectAll = () => {
    if (!data) return;
    if (selectedIds.size === data.items.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(data.items.map((c) => c.id)));
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSingleDelete = async () => {
    if (!deleteId) return;
    try {
      await deleteCase.mutateAsync(deleteId);
      toast.success("用例已删除");
    } catch {
      toast.error("删除失败");
    }
    setDeleteId(null);
  };

  const handleBatchDelete = async () => {
    if (selectedIds.size === 0) return;
    try {
      await Promise.all([...selectedIds].map((id) => deleteCase.mutateAsync(id)));
      toast.success(`已删除 ${selectedIds.size} 个用例`);
      setSelectedIds(new Set());
    } catch {
      toast.error("批量删除失败");
    }
    setBatchDeleteOpen(false);
  };

  const formatDate = (dateStr: string) => {
    try {
      return format(new Date(dateStr), "MM-dd HH:mm", { locale: zhCN });
    } catch {
      return dateStr;
    }
  };

  const totalPages = data?.pagination.total_pages || 1;
  const isAllSelected = data ? selectedIds.size === data.items.length && data.items.length > 0 : false;

  const generatePageRange = () => {
    const pages: (number | "...")[] = [];
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i);
    } else {
      pages.push(1);
      if (page > 3) pages.push("...");
      for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
        pages.push(i);
      }
      if (page < totalPages - 2) pages.push("...");
      pages.push(totalPages);
    }
    return pages;
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">用例管理</h1>
        {canEdit && (
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={() => navigate("/cases/import")}
            className="gap-2"
          >
            <Upload className="h-4 w-4" />
            从 OpenAPI 导入
          </Button>
          <Button onClick={() => navigate("/cases/new")} className="gap-2">
            <Plus className="h-4 w-4" />
            新建用例
          </Button>
        </div>
        )}
      </div>

      {/* Search + Priority Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder='搜索用例名称... (⌘K 全局搜索)'
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="pl-9 pr-4"
            onFocus={() => setCmdOpen(true)}
          />
        </div>
        <div className="flex gap-1 bg-muted rounded-lg p-1">
          <Button
            variant={priority === "all" ? "default" : "ghost"}
            size="sm"
            onClick={() => setSearchParams((prev) => { const n = new URLSearchParams(prev); n.delete("priority"); n.set("page","1"); return n; })}
          >
            全部
          </Button>
          {PRIORITIES.map((p) => (
            <Button
              key={p}
              variant={priority === p ? "default" : "ghost"}
              size="sm"
              onClick={() => setSearchParams((prev) => { const n = new URLSearchParams(prev); n.set("priority", p); n.set("page","1"); return n; })}
            >
              {p}
            </Button>
          ))}
        </div>
      </div>

      {/* Batch actions bar */}
      {canEdit && selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/30 px-4 py-2">
          <span className="text-sm font-medium">
            已选 {selectedIds.size} 项
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={() => setSelectedIds(new Set())}
            className="gap-1"
          >
            <XSquare className="h-3.5 w-3.5" />
            取消选择
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => setBatchDeleteOpen(true)}
            className="gap-1 ml-auto"
          >
            <Trash2 className="h-3.5 w-3.5" />
            批量删除
          </Button>
        </div>
      )}

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-0">
              {/* Table header skeleton */}
              <div className="flex items-center gap-4 pb-3 border-b">
                <Skeleton className="h-4 w-6" />
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-16 ml-auto" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-24" />
              </div>
              {Array.from({ length: 8 }).map((_, i) => (
                <div
                  key={i}
                  className="flex items-center gap-4 py-3 border-b last:border-0"
                >
                  <Skeleton className="h-4 w-4 rounded" />
                  <div className="flex-1 space-y-1.5">
                    <Skeleton className="h-4 w-48" />
                    <Skeleton className="h-3 w-32" />
                  </div>
                  <div className="flex gap-1">
                    <Skeleton className="h-5 w-12 rounded-full" />
                    <Skeleton className="h-5 w-10 rounded-full" />
                  </div>
                  <Skeleton className="h-5 w-10 rounded-full" />
                  <Skeleton className="h-4 w-8" />
                  <Skeleton className="h-4 w-16" />
                  <div className="flex gap-1">
                    <Skeleton className="h-8 w-8 rounded" />
                    <Skeleton className="h-8 w-8 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : isError ? (
            <div className="p-12 text-center text-destructive">
              加载失败，请检查后端服务是否启动。
            </div>
          ) : data && data.items.length > 0 ? (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <Checkbox
                        checked={isAllSelected}
                        onCheckedChange={toggleSelectAll}
                      />
                    </TableHead>
                    <TableHead>用例名称</TableHead>
                    <TableHead className="w-[200px]">标签</TableHead>
                    <TableHead className="w-[80px]">优先级</TableHead>
                    <TableHead className="w-[80px]">版本</TableHead>
                    <TableHead className="w-[140px]">更新时间</TableHead>
                    <TableHead className="w-[120px]">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.items.map((c: TestCase) => (
                    <TableRow
                      key={c.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate(`/cases/${c.id}/edit`)}
                    >
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Checkbox
                          checked={selectedIds.has(c.id)}
                          onCheckedChange={() => toggleSelect(c.id)}
                        />
                      </TableCell>
                      <TableCell>
                        <div>
                          <p className="font-medium">{c.name}</p>
                          {c.description && (
                            <p className="text-xs text-muted-foreground mt-0.5 line-clamp-1">
                              {c.description}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {c.tags?.slice(0, 3).map((tag: string) => (
                            <Badge key={tag} variant="outline" className="text-xs">
                              {tag}
                            </Badge>
                          ))}
                          {c.tags && c.tags.length > 3 && (
                            <Badge variant="outline" className="text-xs">
                              +{c.tags.length - 3}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={priorityColors[c.priority]}>
                          {c.priority}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        v{c.version}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(c.updated_at)}
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <div className="flex gap-1">
                          {canEdit && (
                            <>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => navigate(`/cases/${c.id}/edit`)}
                              >
                                <Pencil className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => setDeleteId(c.id)}
                              >
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              <div className="flex items-center justify-between px-4 py-3 border-t">
                <span className="text-sm text-muted-foreground">
                  共 {data.pagination.total} 条
                </span>
                <Pagination>
                  <PaginationContent>
                    <PaginationItem>
                      <PaginationPrevious
                        onClick={() => page > 1 && goToPage(page - 1)}
                        className={page <= 1 ? "pointer-events-none opacity-50" : "cursor-pointer"}
                      />
                    </PaginationItem>
                    {generatePageRange().map((p, i) =>
                      p === "..." ? (
                        <PaginationItem key={`ellipsis-${i}`}>
                          <span className="px-2 text-muted-foreground">...</span>
                        </PaginationItem>
                      ) : (
                        <PaginationItem key={p}>
                          <PaginationLink
                            isActive={p === page}
                            onClick={() => goToPage(p as number)}
                          >
                            {p}
                          </PaginationLink>
                        </PaginationItem>
                      )
                    )}
                    <PaginationItem>
                      <PaginationNext
                        onClick={() => page < totalPages && goToPage(page + 1)}
                        className={page >= totalPages ? "pointer-events-none opacity-50" : "cursor-pointer"}
                      />
                    </PaginationItem>
                  </PaginationContent>
                </Pagination>
              </div>
            </>
          ) : (
            <div className="p-12">
              <EmptyState
                icon={FileText}
                title="暂无用例数据"
                description="点击「新建用例」或「从 OpenAPI 导入」开始创建你的第一个测试用例"
                action={canEdit ? { label: "新建用例", onClick: () => navigate("/cases/new") } : undefined}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* ⌘K Command Dialog */}
      <CommandDialog open={cmdOpen} onOpenChange={setCmdOpen}>
        <CommandInput
          placeholder="搜索用例名称..."
          value={searchInput}
          onValueChange={(v) => setSearchInput(v)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              handleSearch();
              setCmdOpen(false);
            }
          }}
        />
        <CommandList>
          <CommandEmpty>无匹配结果</CommandEmpty>
          {data?.items && (
            <CommandGroup heading="用例列表">
              {data.items.map((c: TestCase) => (
                <CommandItem
                  key={c.id}
                  onSelect={() => {
                    navigate(`/cases/${c.id}/edit`);
                    setCmdOpen(false);
                  }}
                >
                  <Search className="mr-2 h-4 w-4" />
                  <div className="flex items-center gap-2">
                    <span>{c.name}</span>
                    <Badge variant={priorityColors[c.priority as CasePriority]} className="text-xs">
                      {c.priority}
                    </Badge>
                  </div>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
        </CommandList>
      </CommandDialog>

      {/* Single Delete AlertDialog */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              此操作不可撤销。确定要删除该用例吗？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleSingleDelete}
              disabled={deleteCase.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteCase.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Batch Delete AlertDialog */}
      <AlertDialog open={batchDeleteOpen} onOpenChange={setBatchDeleteOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认批量删除</AlertDialogTitle>
            <AlertDialogDescription>
              即将删除 {selectedIds.size} 个用例，此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleBatchDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              删除 {selectedIds.size} 个用例
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
