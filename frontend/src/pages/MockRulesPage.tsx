import { useState } from "react";
import {
  useMockRules, useCreateMockRule, useCreateMockRulesBatch,
  useDeleteMockRule, useUpdateMockRule, useClearMockRules,
} from "@/hooks/useMockRules";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem,
  SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogDescription,
  DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import {
  Plus, Pencil, Trash2, Loader2, Server, TrashIcon,
  Play, Copy, CheckCircle2, XCircle,
} from "lucide-react";
import type { MockRule, MockRuleCreate } from "@/types";
import { usePermission } from "@/hooks/usePermission";

const HTTP_METHODS = ["ANY", "GET", "POST", "PUT", "DELETE", "PATCH"];
const STATUS_CODES = ["200", "201", "204", "301", "302", "400", "401", "403", "404", "500", "502", "503"];

type JsonTab = "raw" | "formatted";

export function MockRulesPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<MockRule | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [clearConfirm, setClearConfirm] = useState(false);
  const [jsonTab, setJsonTab] = useState<JsonTab>("formatted");
  const { canEdit } = usePermission();

  const [formData, setFormData] = useState({
    url_pattern: "", method: "ANY", status_code: 200,
    response_body: "", description: "", priority: 0, delay_ms: 0,
  });

  const { data, isLoading, isError } = useMockRules({});
  const createRule = useCreateMockRule();
  const createBatch = useCreateMockRulesBatch();
  const updateRule = useUpdateMockRule();
  const deleteRule = useDeleteMockRule();
  const clearRules = useClearMockRules();

  const openCreate = () => {
    setEditingRule(null);
    setFormData({
      url_pattern: "", method: "ANY", status_code: 200,
      response_body: "", description: "", priority: 0, delay_ms: 0,
    });
    setJsonTab("formatted");
    setDialogOpen(true);
  };

  const openEdit = (rule: MockRule) => {
    setEditingRule(rule);
    setFormData({
      url_pattern: rule.url_pattern,
      method: rule.method,
      status_code: rule.status_code,
      response_body: typeof rule.response_body === "string"
        ? rule.response_body
        : JSON.stringify(rule.response_body, null, 2),
      description: rule.description || "",
      priority: rule.priority,
      delay_ms: rule.delay_ms,
    });
    setJsonTab("formatted");
    setDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    let parsedBody: unknown = formData.response_body;
    if (formData.response_body.trim()) {
      try {
        parsedBody = JSON.parse(formData.response_body);
      } catch {
        // If not valid JSON, treat as plain text
        parsedBody = formData.response_body;
      }
    }

    const payload: MockRuleCreate = {
      url_pattern: formData.url_pattern,
      method: formData.method,
      status_code: formData.status_code,
      response_body: parsedBody || undefined,
      description: formData.description,
      priority: formData.priority,
      delay_ms: formData.delay_ms,
    };

    try {
      if (editingRule) {
        await updateRule.mutateAsync({ id: editingRule.id, payload });
        toast.success("Mock 规则已更新");
      } else {
        await createRule.mutateAsync(payload);
        toast.success("Mock 规则已创建");
      }
      setDialogOpen(false);
    } catch {
      toast.error("保存失败");
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await deleteRule.mutateAsync(deleteId);
      toast.success("规则已删除");
    } catch {
      toast.error("删除失败");
    }
    setDeleteId(null);
  };

  const handleClearAll = async () => {
    try {
      await clearRules.mutateAsync();
      toast.success("所有规则已清空");
    } catch {
      toast.error("清空失败");
    }
    setClearConfirm(false);
  };

  const handleDuplicate = async (rule: MockRule) => {
    const payload: MockRuleCreate = {
      url_pattern: rule.url_pattern,
      method: rule.method,
      status_code: rule.status_code,
      response_body: rule.response_body,
      response_headers: rule.response_headers,
      description: `${rule.description || ""} (副本)`,
      priority: rule.priority,
      delay_ms: rule.delay_ms,
    };
    try {
      await createRule.mutateAsync(payload);
      toast.success("规则已复制");
    } catch {
      toast.error("复制失败");
    }
  };

  const formatBody = (body: unknown): string => {
    if (body === null || body === undefined) return "-";
    if (typeof body === "string") return body;
    try {
      return JSON.stringify(body, null, 2);
    } catch {
      return String(body);
    }
  };

  const getMethodColor = (method: string): "default" | "secondary" | "destructive" | "outline" => {
    switch (method.toUpperCase()) {
      case "GET": return "default";
      case "POST": return "secondary";
      case "PUT": return "outline";
      case "DELETE": return "destructive";
      case "PATCH": return "outline";
      default: return "secondary";
    }
  };

  const rules = data?.rules || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Mock 规则管理</h1>
          <p className="text-sm text-muted-foreground mt-1">
            配置 Mock 规则后，将测试的 base_url 设置为 <code className="bg-muted px-1.5 py-0.5 rounded text-xs">http://host:port/_mock</code> 即可使用
          </p>
        </div>
        <div className="flex gap-2">
          {canEdit && rules.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setClearConfirm(true)}
              className="gap-1.5"
            >
              <TrashIcon className="h-4 w-4" />
              清空全部
            </Button>
          )}
          {canEdit && (
          <Button onClick={openCreate} className="gap-1.5">
            <Plus className="h-4 w-4" />
            新建规则
          </Button>
          )}
        </div>
      </div>

      {/* Loading / Error */}
      {isLoading && (
        <Card>
          <CardContent className="py-8 space-y-3">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </CardContent>
        </Card>
      )}

      {isError && (
        <Card>
          <CardContent className="py-12 text-center text-destructive">
            加载失败，请检查后端 Mock 服务是否已在 /_mock 路径挂载。
          </CardContent>
        </Card>
      )}

      {/* Empty State */}
      {!isLoading && !isError && rules.length === 0 && (
        <Card>
          <CardContent className="py-16 text-center space-y-3">
            <Server className="h-12 w-12 mx-auto text-muted-foreground/40" />
            <div>
              <p className="text-lg font-medium text-muted-foreground">暂无 Mock 规则</p>
              <p className="text-sm text-muted-foreground mt-1">
                点击「新建规则」添加第一条 Mock 规则
              </p>
            </div>
            {canEdit && (
            <Button onClick={openCreate} variant="outline" className="mt-2">
              <Plus className="h-4 w-4 mr-2" />
              新建规则
            </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Rules Table */}
      {!isLoading && !isError && rules.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium flex items-center gap-2">
              <Server className="h-4 w-4" />
              已注册 {data?.total || rules.length} 条规则
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[130px]">方法</TableHead>
                  <TableHead>URL 匹配模式</TableHead>
                  <TableHead className="w-[80px]">状态码</TableHead>
                  <TableHead>响应体预览</TableHead>
                  <TableHead className="w-[50px]">延迟</TableHead>
                  <TableHead className="w-[120px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule) => (
                  <TableRow key={rule.id}>
                    <TableCell>
                      <Badge variant={getMethodColor(rule.method)} className="font-mono">
                        {rule.method}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                        {rule.url_pattern}
                      </code>
                      {rule.description && (
                        <p className="text-xs text-muted-foreground mt-0.5 truncate max-w-[250px]">
                          {rule.description}
                        </p>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className={rule.status_code < 400 ? "text-green-600" : "text-red-600"}>
                        {rule.status_code}
                      </span>
                    </TableCell>
                    <TableCell className="max-w-[200px]">
                      <code className="text-xs text-muted-foreground block truncate font-mono">
                        {formatBody(rule.response_body)}
                      </code>
                    </TableCell>
                    <TableCell>
                      {rule.delay_ms > 0 ? `${rule.delay_ms}ms` : "-"}
                    </TableCell>
                    <TableCell>
                      {canEdit && (
                      <div className="flex gap-0.5">
                        <Button
                          variant="ghost" size="icon"
                          className="h-8 w-8"
                          onClick={() => handleDuplicate(rule)}
                          title="复制"
                        >
                          <Copy className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost" size="icon"
                          className="h-8 w-8"
                          onClick={() => openEdit(rule)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost" size="icon"
                          className="h-8 w-8"
                          onClick={() => setDeleteId(rule.id)}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-destructive" />
                        </Button>
                      </div>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingRule ? "编辑 Mock 规则" : "新建 Mock 规则"}
            </DialogTitle>
            <DialogDescription>
              配置 URL 匹配模式、HTTP 方法和期望的响应数据。
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit}>
            <div className="space-y-4 py-2">
              {/* URL Pattern */}
              <div className="space-y-2">
                <Label htmlFor="mock-url">URL 匹配模式 *</Label>
                <Input
                  id="mock-url"
                  value={formData.url_pattern}
                  onChange={(e) => setFormData((p) => ({ ...p, url_pattern: e.target.value }))}
                  placeholder="/api/users/* or /api/orders/123"
                  required
                />
                <p className="text-xs text-muted-foreground">
                  支持通配符 * 匹配任意路径段。如 /api/users/* 匹配 /api/users/123
                </p>
              </div>

              {/* Method & Status Code */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="mock-method">HTTP 方法</Label>
                  <Select
                    value={formData.method}
                    onValueChange={(v) => setFormData((p) => ({ ...p, method: v }))}
                  >
                    <SelectTrigger id="mock-method">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {HTTP_METHODS.map((m) => (
                        <SelectItem key={m} value={m}>{m}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="mock-status">响应状态码</Label>
                  <Select
                    value={String(formData.status_code)}
                    onValueChange={(v) => setFormData((p) => ({ ...p, status_code: Number(v) }))}
                  >
                    <SelectTrigger id="mock-status">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_CODES.map((c) => (
                        <SelectItem key={c} value={c}>{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Response Body */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>响应体 (JSON / 文本)</Label>
                  <Tabs value={jsonTab} onValueChange={(v) => setJsonTab(v as JsonTab)} className="m-0">
                    <TabsList className="h-7">
                      <TabsTrigger value="formatted" className="text-xs h-6 px-2">格式化</TabsTrigger>
                      <TabsTrigger value="raw" className="text-xs h-6 px-2">原始</TabsTrigger>
                    </TabsList>
                  </Tabs>
                </div>
                <Textarea
                  value={formData.response_body}
                  onChange={(e) => setFormData((p) => ({ ...p, response_body: e.target.value }))}
                  placeholder='{"id": 1, "name": "mock_user"} 或 纯文本内容'
                  rows={jsonTab === "formatted" ? 8 : 3}
                  className="font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  输入 JSON 对象、数组或纯文本。留空则不返回响应体。
                </p>
              </div>

              {/* Description */}
              <div className="space-y-2">
                <Label htmlFor="mock-desc">描述</Label>
                <Input
                  id="mock-desc"
                  value={formData.description}
                  onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
                  placeholder="规则用途说明（可选）"
                />
              </div>

              {/* Priority & Delay */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="mock-priority">优先级</Label>
                  <Input
                    id="mock-priority"
                    type="number"
                    value={formData.priority}
                    onChange={(e) => setFormData((p) => ({ ...p, priority: Number(e.target.value) }))}
                  />
                  <p className="text-xs text-muted-foreground">数值越大越优先匹配</p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="mock-delay">模拟延迟 (ms)</Label>
                  <Input
                    id="mock-delay"
                    type="number"
                    min={0}
                    value={formData.delay_ms}
                    onChange={(e) => setFormData((p) => ({ ...p, delay_ms: Number(e.target.value) }))}
                  />
                  <p className="text-xs text-muted-foreground">0 = 无延迟</p>
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                取消
              </Button>
              <Button
                type="submit"
                disabled={createRule.isPending || updateRule.isPending}
              >
                {(createRule.isPending || updateRule.isPending) && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                保存
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              删除后该 Mock 规则将立即失效。此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleteRule.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteRule.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Clear All Confirmation */}
      <AlertDialog open={clearConfirm} onOpenChange={setClearConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认清空全部规则</AlertDialogTitle>
            <AlertDialogDescription>
              将删除所有 {rules.length} 条 Mock 规则。此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleClearAll}
              disabled={clearRules.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {clearRules.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              清空全部
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
