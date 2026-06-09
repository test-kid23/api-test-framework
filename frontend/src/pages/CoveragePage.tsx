import { useState, useCallback } from "react";
import {
  Search,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Zap,
  Download,
  Eye,
  ChevronDown,
  ChevronRight,
  BarChart3,
  Target,
  PieChart,
  Link,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { coverageApi } from "@/api/coverage";
import { toast } from "sonner";
import type {
  CoverageReport,
  CoverageGap,
  CoverageGroup,
  EndpointInfo,
  GeneratedCaseItem,
} from "@/types";

const httpMethodColors: Record<string, string> = {
  GET: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  POST: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  PUT: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
  DELETE: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  PATCH: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  HEAD: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
  OPTIONS: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

const priorityColors: Record<string, string> = {
  P0: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  P1: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  P2: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  P3: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
};

function getCoverageColor(rate: number): string {
  if (rate >= 80) return "text-emerald-600 dark:text-emerald-400";
  if (rate >= 50) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

function getCoverageBgColor(rate: number): string {
  if (rate >= 80) return "bg-emerald-500";
  if (rate >= 50) return "bg-amber-500";
  return "bg-red-500";
}

export function CoveragePage() {
  const [specUrl, setSpecUrl] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [report, setReport] = useState<CoverageReport | null>(null);
  const [generatedCases, setGeneratedCases] = useState<GeneratedCaseItem[]>([]);
  const [selectedEndpoint, setSelectedEndpoint] = useState<EndpointInfo | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [expandedGaps, setExpandedGaps] = useState(false);

  const handleAnalyze = useCallback(async () => {
    if (!specUrl.trim()) {
      toast.error("请输入 OpenAPI Spec URL");
      return;
    }
    setAnalyzing(true);
    setReport(null);
    setGeneratedCases([]);
    setSelectedEndpoint(null);
    try {
      const result = await coverageApi.analyze({ spec_url: specUrl.trim() });
      setReport(result);
      toast.success(
        `分析完成：覆盖率 ${result.coverage_percent}%，${result.uncovered_endpoints} 个未覆盖`
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "分析失败";
      toast.error(msg);
    } finally {
      setAnalyzing(false);
    }
  }, [specUrl]);

  const handleGenerate = useCallback(async () => {
    if (!specUrl.trim()) {
      toast.error("请输入 OpenAPI Spec URL");
      return;
    }
    setGenerating(true);
    try {
      const result = await coverageApi.generate({ spec_url: specUrl.trim() });
      setGeneratedCases(result.generated_cases);
      if (result.errors.length > 0) {
        toast.warning(`生成了 ${result.total_generated} 个用例，${result.errors.length} 个错误`);
      } else {
        toast.success(`成功生成 ${result.total_generated} 个用例`);
      }
      setActiveTab("generated");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "生成失败";
      toast.error(msg);
    } finally {
      setGenerating(false);
    }
  }, [specUrl]);

  const handleGenerateAndSave = useCallback(async () => {
    if (!specUrl.trim()) {
      toast.error("请输入 OpenAPI Spec URL");
      return;
    }
    setSaving(true);
    try {
      const result = await coverageApi.generateAndSave({ spec_url: specUrl.trim() });
      if (result.total_generated > 0) {
        toast.success(`已生成并保存 ${result.total_generated} 个用例到数据库`);
      }
      if (result.errors.length > 0) {
        result.errors.forEach((e) => toast.error(e));
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "保存失败";
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  }, [specUrl]);

  function handleViewYaml(caseItem: GeneratedCaseItem) {
    const w = window.open("", "_blank", "width=800,height=600");
    if (w) {
      w.document.write(
        `<pre style="padding:16px;font-family:monospace;font-size:13px;white-space:pre-wrap;word-break:break-all;">${escapeHtml(caseItem.yaml_content)}</pre>`
      );
      w.document.title = `${caseItem.method} ${caseItem.path}`;
    }
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight">覆盖率分析</h1>
        <p className="text-sm text-muted-foreground mt-1">
          对比 OpenAPI Spec 与已有用例，识别未覆盖的 API 并推荐生成测试用例
        </p>
      </div>

      {/* Input Bar */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="spec-url" className="mb-2 block">
                OpenAPI Spec URL
              </Label>
              <Input
                id="spec-url"
                placeholder="https://petstore3.swagger.io/api/v3/openapi.json"
                value={specUrl}
                onChange={(e) => setSpecUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
              />
            </div>
            <div className="flex items-end gap-2">
              <Button onClick={handleAnalyze} disabled={analyzing}>
                {analyzing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Search className="mr-2 h-4 w-4" />
                )}
                分析覆盖率
              </Button>
              <Button
                variant="outline"
                onClick={handleGenerate}
                disabled={generating || !specUrl.trim()}
              >
                {generating ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Zap className="mr-2 h-4 w-4" />
                )}
                生成预览
              </Button>
              <Button
                variant="secondary"
                onClick={handleGenerateAndSave}
                disabled={saving || !specUrl.trim()}
              >
                {saving ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Download className="mr-2 h-4 w-4" />
                )}
                一键生成并保存
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Loading State */}
      {analyzing && (
        <div className="space-y-4">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {/* Report */}
      {report && !analyzing && (
        <>
          {/* KPI Cards */}
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">总体覆盖率</CardTitle>
                <Target className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">
                  <span className={getCoverageColor(report.coverage_percent)}>
                    {report.coverage_percent}%
                  </span>
                </div>
                <Progress
                  value={report.coverage_percent}
                  className="mt-2"
                  indicatorClassName={getCoverageBgColor(report.coverage_percent)}
                />
                <p className="text-xs text-muted-foreground mt-2">
                  {report.covered_endpoints} / {report.total_endpoints} endpoints 已覆盖
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">已覆盖</CardTitle>
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-emerald-600 dark:text-emerald-400">
                  {report.covered_endpoints}
                </div>
                <p className="text-xs text-muted-foreground mt-2">已有测试用例的 API</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">未覆盖</CardTitle>
                <AlertTriangle className="h-4 w-4 text-amber-500" />
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-amber-600 dark:text-amber-400">
                  {report.uncovered_endpoints}
                </div>
                <p className="text-xs text-muted-foreground mt-2">需要生成用例的 API</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Spec 信息</CardTitle>
                <Link className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-lg font-semibold truncate">{report.spec_title}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  OpenAPI {report.spec_version} · {report.total_endpoints} endpoints
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Detail Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList>
              <TabsTrigger value="overview">
                <PieChart className="mr-2 h-4 w-4" />
                分组统计
              </TabsTrigger>
              <TabsTrigger value="gaps">
                <AlertTriangle className="mr-2 h-4 w-4" />
                覆盖缺口
                <Badge variant="secondary" className="ml-2">
                  {report.gaps.length}
                </Badge>
              </TabsTrigger>
              <TabsTrigger value="recommendations">
                <Zap className="mr-2 h-4 w-4" />
                推荐生成
                <Badge variant="secondary" className="ml-2">
                  {report.recommendations.length}
                </Badge>
              </TabsTrigger>
              {generatedCases.length > 0 && (
                <TabsTrigger value="generated">
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  已生成用例
                  <Badge variant="secondary" className="ml-2">
                    {generatedCases.length}
                  </Badge>
                </TabsTrigger>
              )}
            </TabsList>

            {/* Overview: 分组统计 */}
            <TabsContent value="overview" className="space-y-4 mt-4">
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <GroupCoverageCard title="按 Method 分组" groups={report.by_method} />
                <GroupCoverageCard title="按 Tag 分组" groups={report.by_tag} />
                <GroupCoverageCard title="按优先级分组" groups={report.by_priority} />
              </div>
            </TabsContent>

            {/* Gaps: 覆盖缺口 */}
            <TabsContent value="gaps" className="mt-4">
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <CardTitle className="text-base">
                    未覆盖的 API Endpoints ({report.gaps.length})
                  </CardTitle>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setExpandedGaps(!expandedGaps)}
                  >
                    {expandedGaps ? "收起" : "展开全部"}
                    <ChevronDown
                      className={`ml-1 h-4 w-4 transition-transform ${expandedGaps ? "rotate-180" : ""}`}
                    />
                  </Button>
                </CardHeader>
                <CardContent>
                  <ScrollArea className={expandedGaps ? "h-[600px]" : "h-[400px]"}>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[80px]">Method</TableHead>
                          <TableHead>Path</TableHead>
                          <TableHead className="w-[120px]">优先级</TableHead>
                          <TableHead className="w-[100px]">Tags</TableHead>
                          <TableHead className="w-[120px]">相似用例</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {report.gaps.map((gap, i) => (
                          <TableRow
                            key={`${gap.endpoint.method}-${gap.endpoint.path}-${i}`}
                            className="cursor-pointer hover:bg-muted/50"
                            onClick={() => setSelectedEndpoint(gap.endpoint)}
                          >
                            <TableCell>
                              <Badge
                                variant="outline"
                                className={httpMethodColors[gap.endpoint.method] || ""}
                              >
                                {gap.endpoint.method}
                              </Badge>
                            </TableCell>
                            <TableCell className="font-mono text-sm">
                              {gap.endpoint.path}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant="outline"
                                className={priorityColors[gap.endpoint.priority] || ""}
                              >
                                {gap.endpoint.priority}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <div className="flex flex-wrap gap-1">
                                {gap.endpoint.tags.slice(0, 2).map((t) => (
                                  <Badge key={t} variant="secondary" className="text-xs">
                                    {t}
                                  </Badge>
                                ))}
                                {gap.endpoint.tags.length > 2 && (
                                  <span className="text-xs text-muted-foreground">
                                    +{gap.endpoint.tags.length - 2}
                                  </span>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>
                              {gap.has_similar ? (
                                <Badge variant="outline" className="text-amber-600 border-amber-300">
                                  有相似
                                </Badge>
                              ) : (
                                <Badge variant="outline" className="text-muted-foreground">
                                  全新
                                </Badge>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Recommendations */}
            <TabsContent value="recommendations" className="mt-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    推荐生成的用例 ({report.recommendations.length})
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ScrollArea className="h-[400px]">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-[50px]">#</TableHead>
                          <TableHead className="w-[80px]">Method</TableHead>
                          <TableHead>Path</TableHead>
                          <TableHead className="w-[120px]">优先级</TableHead>
                          <TableHead>摘要</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {report.recommendations.map((ep, i) => (
                          <TableRow key={`${ep.method}-${ep.path}-${i}`}>
                            <TableCell className="text-muted-foreground">{i + 1}</TableCell>
                            <TableCell>
                              <Badge
                                variant="outline"
                                className={httpMethodColors[ep.method] || ""}
                              >
                                {ep.method}
                              </Badge>
                            </TableCell>
                            <TableCell className="font-mono text-sm">{ep.path}</TableCell>
                            <TableCell>
                              <Badge
                                variant="outline"
                                className={priorityColors[ep.priority] || ""}
                              >
                                {ep.priority}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground max-w-[300px] truncate">
                              {ep.summary || ep.operation_id || "-"}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </ScrollArea>
                </CardContent>
              </Card>
            </TabsContent>

            {/* Generated Cases */}
            {generatedCases.length > 0 && (
              <TabsContent value="generated" className="mt-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">
                      已生成的用例 ({generatedCases.length})
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ScrollArea className="h-[500px]">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead className="w-[80px]">Method</TableHead>
                            <TableHead>Path</TableHead>
                            <TableHead>用例名称</TableHead>
                            <TableHead className="w-[80px]">优先级</TableHead>
                            <TableHead className="w-[100px]">操作</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {generatedCases.map((c, i) => (
                            <TableRow key={`${c.method}-${c.path}-${i}`}>
                              <TableCell>
                                <Badge
                                  variant="outline"
                                  className={httpMethodColors[c.method] || ""}
                                >
                                  {c.method}
                                </Badge>
                              </TableCell>
                              <TableCell className="font-mono text-sm">{c.path}</TableCell>
                              <TableCell className="font-medium">{c.name}</TableCell>
                              <TableCell>
                                <Badge
                                  variant="outline"
                                  className={priorityColors[c.priority] || ""}
                                >
                                  {c.priority}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleViewYaml(c)}
                                >
                                  <Eye className="mr-1 h-3 w-3" />
                                  查看
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </ScrollArea>
                  </CardContent>
                </Card>
              </TabsContent>
            )}
          </Tabs>
        </>
      )}

      {/* Empty State */}
      {!report && !analyzing && (
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-16">
            <BarChart3 className="h-16 w-16 text-muted-foreground/30 mb-4" />
            <h3 className="text-lg font-semibold text-muted-foreground mb-2">
              输入 OpenAPI Spec URL 开始分析
            </h3>
            <p className="text-sm text-muted-foreground/70 max-w-md text-center">
              支持 OpenAPI 3.x 规范（JSON/YAML），系统将自动对比已有用例，
              计算 API 覆盖率并推荐生成缺失的测试用例
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────

function GroupCoverageCard({
  title,
  groups,
}: {
  title: string;
  groups: CoverageGroup[];
}) {
  if (groups.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">暂无数据</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {groups.map((g) => (
          <div key={g.group_key} className="space-y-1">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{g.group_key}</span>
              <span className={getCoverageColor(g.coverage_rate * 100)}>
                {(g.coverage_rate * 100).toFixed(1)}%
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Progress
                value={g.coverage_rate * 100}
                className="flex-1"
                indicatorClassName={getCoverageBgColor(g.coverage_rate * 100)}
              />
              <span className="text-xs text-muted-foreground whitespace-nowrap">
                {g.covered}/{g.total}
              </span>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ── Utils ──────────────────────────────────────────────────

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
