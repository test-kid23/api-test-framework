import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Pencil, Play, Copy, Calendar, Tag, Clock, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { toast } from "sonner";
import { useCase } from "@/hooks/useCases";
import { casesApi } from "@/api/cases";
import { executionsApi } from "@/api/executions";

const priorityColors: Record<string, string> = {
  P0: "border-red-200 bg-red-50 text-red-700",
  P1: "border-orange-200 bg-orange-50 text-orange-700",
  P2: "border-blue-200 bg-blue-50 text-blue-700",
  P3: "border-slate-200 bg-slate-50 text-slate-600",
};

export function CaseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: testCase, isLoading } = useCase(id);
  const [versions, setVersions] = useState<{ version: number; created_at: string }[]>([]);
  const [versionsLoaded, setVersionsLoaded] = useState(false);
  const [executing, setExecuting] = useState(false);

  // Load version history
  useEffect(() => {
    if (id && !versionsLoaded) {
      casesApi.getVersions(id).then(setVersions).catch(() => {}).finally(() => setVersionsLoaded(true));
    }
  }, [id, versionsLoaded]);

  async function handleExecute() {
    if (!id) return;
    setExecuting(true);
    try {
      const result = await executionsApi.trigger({
        case_ids: [id],
      });
      toast.success(`执行已触发: ${result.name}`);
      navigate(`/executions/${result.id}`);
    } catch {
      toast.error("触发执行失败");
    } finally {
      setExecuting(false);
    }
  }

  function handleCopy() {
    if (testCase) {
      navigator.clipboard.writeText(testCase.yaml_content);
      toast.success("YAML 内容已复制到剪贴板");
    }
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleString("zh-CN");
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/cases")}>
          <ArrowLeft className="mr-1 h-4 w-4" />返回
        </Button>
        <div className="flex-1" />
        <Button variant="outline" size="sm" onClick={handleCopy}>
          <Copy className="mr-1 h-4 w-4" />复制 YAML
        </Button>
        <Button variant="outline" size="sm" onClick={() => navigate(`/cases/${id}/edit`)}>
          <Pencil className="mr-1 h-4 w-4" />编辑
        </Button>
        <Button size="sm" onClick={handleExecute} disabled={executing}>
          <Play className="mr-1 h-4 w-4" />
          {executing ? "触发中..." : "执行"}
        </Button>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-4 w-1/3" />
          <Skeleton className="h-64 w-full" />
        </div>
      ) : testCase ? (
        <div className="grid gap-6 lg:grid-cols-5">
          {/* Left: Info */}
          <div className="lg:col-span-2 space-y-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-xl">{testCase.name}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {testCase.description && (
                  <div>
                    <p className="text-sm text-muted-foreground">{testCase.description}</p>
                  </div>
                )}
                <div className="grid grid-cols-2 gap-3">
                  <div className="flex items-center gap-2 text-sm">
                    <Tag className="h-4 w-4 text-muted-foreground" />
                    <Badge className={priorityColors[testCase.priority] || ""}>
                      {testCase.priority}
                    </Badge>
                  </div>
                  {testCase.timeout && (
                    <div className="flex items-center gap-2 text-sm">
                      <Clock className="h-4 w-4 text-muted-foreground" />
                      <span className="text-muted-foreground">{testCase.timeout}s 超时</span>
                    </div>
                  )}
                </div>
                <Separator />
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-sm">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">
                      创建于 {formatDate(testCase.created_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <Calendar className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">
                      更新于 {formatDate(testCase.updated_at)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-sm">
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <span className="text-muted-foreground">版本 v{testCase.version}</span>
                  </div>
                </div>
                {testCase.tags.length > 0 && (
                  <>
                    <Separator />
                    <div>
                      <p className="text-xs font-medium text-muted-foreground mb-2">标签</p>
                      <div className="flex flex-wrap gap-1.5">
                        {testCase.tags.map((tag) => (
                          <Badge key={tag} variant="secondary" className="text-xs">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>

            {/* Version History */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">版本历史</CardTitle>
              </CardHeader>
              <CardContent>
                {versions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {versionsLoaded ? "暂无版本记录" : "加载中..."}
                  </p>
                ) : (
                  <div className="space-y-2">
                    {versions.map((v, i) => (
                      <div
                        key={v.version}
                        className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
                      >
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className="text-xs">
                            v{v.version}
                          </Badge>
                          {i === 0 && (
                            <Badge className="text-xs bg-emerald-50 text-emerald-700 border-emerald-200">
                              当前
                            </Badge>
                          )}
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {formatDate(v.created_at)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Right: YAML Content */}
          <div className="lg:col-span-3">
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">YAML 内容</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[600px] rounded-md border bg-muted/30">
                  <pre className="p-4 text-sm font-mono leading-relaxed whitespace-pre-wrap break-all">
                    <code>{testCase.yaml_content}</code>
                  </pre>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </div>
      ) : (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16">
            <FileText className="h-12 w-12 text-muted-foreground/50" />
            <p className="mt-4 text-sm text-muted-foreground">用例不存在</p>
            <Button
              variant="outline"
              className="mt-4"
              onClick={() => navigate("/cases")}
            >
              返回列表
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
