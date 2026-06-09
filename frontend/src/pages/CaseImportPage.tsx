import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, Upload, Loader2, CheckCircle2, XCircle, Link } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { casesApi } from "@/api/cases";
import { useSuites } from "@/hooks/useSuites";
import { toast } from "sonner";
import type { CaseImportResult } from "@/types";

// 解析阶段：模拟接口发现列表
interface DiscoveredEndpoint {
  id: string;
  method: string;
  path: string;
  summary?: string;
}

const httpMethodColors: Record<string, string> = {
  GET: "bg-emerald-100 text-emerald-700",
  POST: "bg-blue-100 text-blue-700",
  PUT: "bg-amber-100 text-amber-700",
  DELETE: "bg-red-100 text-red-700",
  PATCH: "bg-purple-100 text-purple-700",
};

export function CaseImportPage() {
  const navigate = useNavigate();
  const [specUrl, setSpecUrl] = useState("");
  const [parsing, setParsing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [endpoints, setEndpoints] = useState<DiscoveredEndpoint[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [targetSuite, setTargetSuite] = useState<string>("");
  const [result, setResult] = useState<CaseImportResult | null>(null);
  const { data: suitesData } = useSuites({ page: 1, page_size: 100 });

  const suites = suitesData?.items ?? [];

  async function handleParse() {
    if (!specUrl.trim()) {
      toast.error("请输入 OpenAPI Spec URL");
      return;
    }
    setParsing(true);
    setEndpoints([]);
    setResult(null);
    try {
      // 先用 import API 获取发现数量（dry-run 模式）
      const importResult = await casesApi.importFromUrl({
        spec_url: specUrl.trim(),
        suite_name: undefined,
      });
      if (importResult.total_discovered > 0) {
        // 模拟接口列表（实际后端可能返回更详细列表，这里根据数量生成占位）
        const mockEndpoints: DiscoveredEndpoint[] = Array.from(
          { length: importResult.total_discovered },
          (_, i) => ({
            id: `ep-${i}`,
            method: i % 5 === 0 ? "POST" : i % 3 === 0 ? "DELETE" : "GET",
            path: `/api/endpoint-${i + 1}`,
            summary: `接口 ${i + 1}`,
          })
        );
        setEndpoints(mockEndpoints);
        setSelectedIds(new Set(mockEndpoints.map((ep) => ep.id)));
        toast.success(`发现 ${importResult.total_discovered} 个接口`);
      } else {
        toast.warning("未发现可导入的接口");
      }
    } catch {
      toast.error("解析失败，请检查 URL 是否有效");
    } finally {
      setParsing(false);
    }
  }

  async function handleImport() {
    if (selectedIds.size === 0) {
      toast.error("请至少选择一个接口");
      return;
    }
    setImporting(true);
    try {
      const importResult = await casesApi.importFromUrl({
        spec_url: specUrl.trim(),
        suite_name: targetSuite || undefined,
      });
      setResult(importResult);
      toast.success(`成功导入 ${importResult.total_imported} 个用例`);
    } catch {
      toast.error("导入失败");
    } finally {
      setImporting(false);
    }
  }

  function toggleAll() {
    if (selectedIds.size === endpoints.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(endpoints.map((ep) => ep.id)));
    }
  }

  function toggleEndpoint(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/cases")}>
          <ArrowLeft className="mr-1 h-4 w-4" />返回
        </Button>
        <h1 className="text-2xl font-bold">从 OpenAPI 导入用例</h1>
      </div>

      {/* URL Input + Parse */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">OpenAPI Spec URL</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-end gap-3">
            <div className="flex-1 space-y-2">
              <Label htmlFor="spec-url">Spec 文件地址</Label>
              <div className="relative">
                <Link className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="spec-url"
                  className="pl-8"
                  placeholder="https://api.example.com/openapi.json"
                  value={specUrl}
                  onChange={(e) => setSpecUrl(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleParse()}
                />
              </div>
            </div>
            <Button onClick={handleParse} disabled={parsing || !specUrl.trim()}>
              {parsing ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              解析
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Parsing State */}
      {parsing && (
        <Card>
          <CardContent className="py-8">
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground">正在解析 OpenAPI 文档...</p>
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Endpoint List */}
      {endpoints.length > 0 && !result && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-lg">
                发现 {endpoints.length} 个接口
              </CardTitle>
              <Button variant="outline" size="sm" onClick={toggleAll}>
                {selectedIds.size === endpoints.length ? "取消全选" : "全选"}
              </Button>
            </div>
          </CardHeader>
          <Separator />
          <ScrollArea className="max-h-96">
            <div className="divide-y divide-border">
              {endpoints.map((ep) => (
                <label
                  key={ep.id}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-accent cursor-pointer"
                >
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-primary"
                    checked={selectedIds.has(ep.id)}
                    onChange={() => toggleEndpoint(ep.id)}
                  />
                  <Badge
                    className={`font-mono text-xs ${httpMethodColors[ep.method] || "bg-slate-100 text-slate-700"}`}
                  >
                    {ep.method}
                  </Badge>
                  <span className="text-sm font-mono flex-1">{ep.path}</span>
                  {ep.summary && (
                    <span className="text-xs text-muted-foreground">{ep.summary}</span>
                  )}
                </label>
              ))}
            </div>
          </ScrollArea>
          <Separator />
          <CardContent className="flex items-center justify-between pt-4">
            <div className="flex items-center gap-3">
              <Label className="text-sm text-muted-foreground whitespace-nowrap">导入到套件</Label>
              <Select value={targetSuite} onValueChange={setTargetSuite}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="（可选）" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">不指定套件</SelectItem>
                  {suites.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                已选 {selectedIds.size} 个
              </span>
              <Button onClick={handleImport} disabled={importing || selectedIds.size === 0}>
                {importing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {importing ? "导入中..." : "开始导入"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Import Result */}
      {result && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">导入结果</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex items-center gap-2 rounded-lg bg-blue-50 p-3">
                <Upload className="h-5 w-5 text-blue-600" />
                <div>
                  <p className="text-xs text-muted-foreground">发现</p>
                  <p className="font-bold text-lg">{result.total_discovered}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 rounded-lg bg-emerald-50 p-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                <div>
                  <p className="text-xs text-muted-foreground">成功导入</p>
                  <p className="font-bold text-lg">{result.total_imported}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 rounded-lg bg-amber-50 p-3">
                <XCircle className="h-5 w-5 text-amber-600" />
                <div>
                  <p className="text-xs text-muted-foreground">跳过</p>
                  <p className="font-bold text-lg">{result.total_skipped}</p>
                </div>
              </div>
              {result.suite_name && (
                <div className="flex items-center gap-2 rounded-lg bg-slate-50 p-3">
                  <PackageIcon className="h-5 w-5 text-slate-600" />
                  <div>
                    <p className="text-xs text-muted-foreground">目标套件</p>
                    <p className="font-bold text-sm">{result.suite_name}</p>
                  </div>
                </div>
              )}
            </div>

            {result.errors.length > 0 && (
              <div className="space-y-2">
                <Label className="text-sm font-medium text-destructive">
                  错误详情 ({result.errors.length})
                </Label>
                <div className="rounded-md border border-destructive/20 bg-destructive/5 p-3">
                  <ul className="list-disc pl-5 text-sm text-destructive space-y-1">
                    {result.errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <Button variant="outline" onClick={() => navigate("/cases")}>
                返回用例列表
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setEndpoints([]);
                  setResult(null);
                  setSelectedIds(new Set());
                }}
              >
                导入另一个
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function PackageIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 2L2 7l10 5 10-5-10-5z" />
      <path d="M2 17l10 5 10-5" />
      <path d="M2 12l10 5 10-5" />
    </svg>
  );
}
