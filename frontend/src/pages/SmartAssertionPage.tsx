import { useState, useEffect } from "react";
import { useSmartAssertion } from "@/hooks/useSmartAssertion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import {
  Sparkles, AlertTriangle, CheckCircle2, Info,
  XCircle, Loader2, Trash2, Search,
} from "lucide-react";
import type { FieldSchemaInfo, AssertionItemInfo, StructureChangeInfo } from "@/types";

const SEVERITY_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  error: { icon: XCircle, color: "text-red-500", label: "错误" },
  warning: { icon: AlertTriangle, color: "text-yellow-500", label: "警告" },
  info: { icon: Info, color: "text-blue-500", label: "提示" },
};

function FieldRow({ field }: { field: FieldSchemaInfo }) {
  return (
    <TableRow>
      <TableCell className="font-mono text-xs max-w-[200px] truncate" title={field.path}>
        {field.path}
      </TableCell>
      <TableCell>
        <Badge variant="outline" className="text-xs">
          {field.dominant_type}
        </Badge>
      </TableCell>
      <TableCell>
        {field.required ? (
          <Badge variant="destructive" className="text-xs">必填</Badge>
        ) : (
          <span className="text-xs text-muted-foreground">
            {Math.round(field.occurrence_rate * 100)}%
          </span>
        )}
      </TableCell>
      <TableCell>
        <span className="text-xs text-muted-foreground">
          {field.min_value != null && field.max_value != null
            ? `[${field.min_value}, ${field.max_value}]`
            : field.value_pattern || "-"}
        </span>
      </TableCell>
      <TableCell>
        {field.warnings.length > 0 ? (
          <Badge variant="secondary" className="text-xs">
            <AlertTriangle className="h-3 w-3 mr-1" />
            {field.warnings[0]}
          </Badge>
        ) : (
          <CheckCircle2 className="h-4 w-4 text-green-500" />
        )}
      </TableCell>
    </TableRow>
  );
}

function AssertionRow({ item }: { item: AssertionItemInfo }) {
  const opColors: Record<string, string> = {
    eq: "bg-blue-50 text-blue-700",
    ne: "bg-orange-50 text-orange-700",
    not_null: "bg-green-50 text-green-700",
    is_null: "bg-gray-50 text-gray-700",
    type: "bg-purple-50 text-purple-700",
    in: "bg-cyan-50 text-cyan-700",
    between: "bg-pink-50 text-pink-700",
    length: "bg-teal-50 text-teal-700",
    lt: "bg-yellow-50 text-yellow-700",
    gt: "bg-amber-50 text-amber-700",
  };

  const expectedStr = typeof item.expected === "object"
    ? JSON.stringify(item.expected)
    : String(item.expected ?? "");

  return (
    <TableRow>
      <TableCell className="font-mono text-xs">{item.path}</TableCell>
      <TableCell>
        <Badge className={`text-xs ${opColors[item.operator] || "bg-gray-50 text-gray-700"}`}>
          {item.operator}
        </Badge>
      </TableCell>
      <TableCell className="font-mono text-xs max-w-[200px] truncate" title={expectedStr}>
        {expectedStr}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground max-w-[250px] truncate" title={item.message}>
        {item.message}
      </TableCell>
    </TableRow>
  );
}

function ChangeRow({ change }: { change: StructureChangeInfo }) {
  const config = SEVERITY_CONFIG[change.severity] || SEVERITY_CONFIG.info;
  const Icon = config.icon;

  return (
    <TableRow>
      <TableCell>
        <Icon className={`h-4 w-4 ${config.color}`} />
      </TableCell>
      <TableCell>
        <Badge variant="outline" className="text-xs">{config.label}</Badge>
      </TableCell>
      <TableCell className="font-mono text-xs">{change.path}</TableCell>
      <TableCell>
        <Badge variant="outline" className="text-xs">{change.change_type}</Badge>
      </TableCell>
      <TableCell className="font-mono text-xs max-w-[150px] truncate">
        {String(change.expected ?? "-")}
      </TableCell>
      <TableCell className="font-mono text-xs max-w-[150px] truncate">
        {String(change.actual ?? "-")}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate" title={change.message}>
        {change.message}
      </TableCell>
    </TableRow>
  );
}

export function SmartAssertionPage() {
  const {
    schema,
    assertions,
    changes,
    changeSummary,
    loading,
    error,
    inferSchema,
    fetchSchema,
    fetchAssertions,
    detectChanges,
    clearSchema,
    reset,
  } = useSmartAssertion();

  const [caseId, setCaseId] = useState("");
  const [sampleLimit, setSampleLimit] = useState(50);
  const [activeTab, setActiveTab] = useState("schema");

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  const handleInfer = async () => {
    if (!caseId.trim()) {
      toast.error("请输入用例 ID");
      return;
    }
    await inferSchema(caseId.trim(), sampleLimit);
    setActiveTab("schema");
    toast.success("Schema 推断完成");
  };

  const handleFetchAssertions = async () => {
    if (!caseId.trim()) return;
    await fetchAssertions(caseId.trim());
    setActiveTab("assertions");
    toast.success("断言生成完成");
  };

  const handleDetect = async () => {
    if (!caseId.trim()) return;
    await detectChanges(caseId.trim());
    setActiveTab("changes");
    if (changes.length === 0) {
      toast.success("未检测到结构变更");
    } else {
      toast.warning(`检测到 ${changes.length} 项变更`);
    }
  };

  const handleClear = async () => {
    if (!caseId.trim()) return;
    await clearSchema(caseId.trim());
    reset();
    toast.success("Schema 已清除");
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-primary" />
            智能断言
          </h1>
          <p className="text-muted-foreground mt-1">
            基于历史成功响应自动推断 Schema，生成智能断言，检测响应结构变更
          </p>
        </div>
        <div className="flex items-center gap-2">
          {schema && (
            <Button variant="outline" size="sm" onClick={handleClear}>
              <Trash2 className="h-4 w-4 mr-1" />
              清除 Schema
            </Button>
          )}
        </div>
      </div>

      {/* Input Card */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">配置推断参数</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-4">
            <div className="flex-1 space-y-2">
              <Label htmlFor="caseId">用例 ID</Label>
              <Input
                id="caseId"
                placeholder="例如: a1b2c3d4e5f6"
                value={caseId}
                onChange={(e) => setCaseId(e.target.value)}
              />
            </div>
            <div className="w-32 space-y-2">
              <Label htmlFor="sampleLimit">样本数</Label>
              <Input
                id="sampleLimit"
                type="number"
                min={1}
                max={200}
                value={sampleLimit}
                onChange={(e) => setSampleLimit(Number(e.target.value))}
              />
            </div>
            <Button onClick={handleInfer} disabled={loading || !caseId.trim()}>
              {loading ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <Search className="h-4 w-4 mr-1" />}
              推断 Schema
            </Button>
            {schema && (
              <>
                <Button variant="secondary" onClick={handleFetchAssertions} disabled={loading}>
                  <Sparkles className="h-4 w-4 mr-1" />
                  生成断言
                </Button>
                <Button variant="outline" onClick={handleDetect} disabled={loading}>
                  <AlertTriangle className="h-4 w-4 mr-1" />
                  检测变更
                </Button>
              </>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Schema Summary */}
      {schema && (
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{Object.keys(schema.fields || {}).length}</div>
              <div className="text-xs text-muted-foreground">字段总数</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">
                {Object.values(schema.fields || {}).filter((f) => f.required).length}
              </div>
              <div className="text-xs text-muted-foreground">必填字段</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{schema.response_count}</div>
              <div className="text-xs text-muted-foreground">成功样本数</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-2xl font-bold">{schema.top_level_type}</div>
              <div className="text-xs text-muted-foreground">顶层类型</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Loading State */}
      {loading && !schema && (
        <div className="space-y-4">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {/* Tabs: Schema / Assertions / Changes */}
      {schema && (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="schema">Schema 详情</TabsTrigger>
            <TabsTrigger value="assertions">
              断言列表 {assertions.length > 0 && `(${assertions.length})`}
            </TabsTrigger>
            <TabsTrigger value="changes">
              变更检测 {changes.length > 0 && `(${changes.length})`}
            </TabsTrigger>
          </TabsList>

          {/* Schema Tab */}
          <TabsContent value="schema" className="mt-4">
            <Card>
              <CardContent className="pt-6">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>字段路径</TableHead>
                      <TableHead>类型</TableHead>
                      <TableHead>必填</TableHead>
                      <TableHead>值范围/模式</TableHead>
                      <TableHead>状态</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {Object.values(schema.fields || {}).map((field) => (
                      <FieldRow key={field.path} field={field} />
                    ))}
                  </TableBody>
                </Table>
                {Object.keys(schema.fields || {}).length === 0 && (
                  <div className="py-8 text-center text-muted-foreground">
                    未推断出字段信息
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Assertions Tab */}
          <TabsContent value="assertions" className="mt-4">
            <Card>
              <CardContent className="pt-6">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>路径</TableHead>
                      <TableHead>操作符</TableHead>
                      <TableHead>期望值</TableHead>
                      <TableHead>说明</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {assertions.map((item, idx) => (
                      <AssertionRow key={`${item.path}-${idx}`} item={item} />
                    ))}
                  </TableBody>
                </Table>
                {assertions.length === 0 && (
                  <div className="py-8 text-center text-muted-foreground">
                    尚未生成断言，请先点击"生成断言"
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Changes Tab */}
          <TabsContent value="changes" className="mt-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">结构变更检测</CardTitle>
                  {changeSummary && (
                    <Badge variant={changes.some(c => c.severity === "error") ? "destructive" : "secondary"}>
                      {changeSummary}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-8"></TableHead>
                      <TableHead>严重度</TableHead>
                      <TableHead>路径</TableHead>
                      <TableHead>类型</TableHead>
                      <TableHead>期望</TableHead>
                      <TableHead>实际</TableHead>
                      <TableHead>说明</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {changes.map((change, idx) => (
                      <ChangeRow key={`${change.path}-${idx}`} change={change} />
                    ))}
                  </TableBody>
                </Table>
                {changes.length === 0 && (
                  <div className="py-8 text-center text-muted-foreground">
                    <CheckCircle2 className="h-12 w-12 mx-auto mb-2 text-green-500" />
                    响应结构与推断 Schema 一致，未检测到变更
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}
