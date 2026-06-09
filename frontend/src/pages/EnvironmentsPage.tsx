import { useState } from "react";
import {
  useEnvironments, useCreateEnvironment,
  useDeleteEnvironment, useUpdateEnvironment,
} from "@/hooks/useEnvironments";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog, DialogContent, DialogDescription,
  DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Loader2, Globe, Wifi } from "lucide-react";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";
import type { Environment } from "@/types";

interface VariableRow {
  key: string;
  value: string;
}

export function EnvironmentsPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingEnv, setEditingEnv] = useState<Environment | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: "", description: "", base_url: "", ws_url: "",
  });
  const [variables, setVariables] = useState<VariableRow[]>([{ key: "", value: "" }]);

  const { data, isLoading, isError } = useEnvironments({ page_size: 20 });
  const createEnv = useCreateEnvironment();
  const updateEnv = useUpdateEnvironment();
  const deleteEnv = useDeleteEnvironment();

  const openCreate = () => {
    setEditingEnv(null);
    setFormData({ name: "", description: "", base_url: "", ws_url: "" });
    setVariables([{ key: "", value: "" }]);
    setDialogOpen(true);
  };

  const openEdit = (env: Environment) => {
    setEditingEnv(env);
    setFormData({
      name: env.name,
      description: env.description || "",
      base_url: env.base_url,
      ws_url: env.ws_url || "",
    });
    const vars = env.variables
      ? Object.entries(env.variables).map(([k, v]) => ({ key: k, value: v }))
      : [{ key: "", value: "" }];
    setVariables(vars.length > 0 ? vars : [{ key: "", value: "" }]);
    setDialogOpen(true);
  };

  const addVariableRow = () => {
    setVariables((prev) => [...prev, { key: "", value: "" }]);
  };

  const removeVariableRow = (idx: number) => {
    setVariables((prev) => prev.filter((_, i) => i !== idx));
  };

  const updateVariableRow = (idx: number, field: "key" | "value", val: string) => {
    setVariables((prev) =>
      prev.map((v, i) => (i === idx ? { ...v, [field]: val } : v))
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Build variables object from rows
    const varsObj: Record<string, string> = {};
    variables.forEach((v) => {
      if (v.key.trim()) varsObj[v.key.trim()] = v.value;
    });

    const payload = {
      ...formData,
      variables: varsObj,
    };

    try {
      if (editingEnv) {
        await updateEnv.mutateAsync({ id: editingEnv.id, payload });
        toast.success("环境已更新");
      } else {
        await createEnv.mutateAsync(payload);
        toast.success("环境已创建");
      }
      setDialogOpen(false);
    } catch {
      toast.error("保存失败");
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    try {
      await deleteEnv.mutateAsync(deleteId);
      toast.success("环境已删除");
    } catch {
      toast.error("删除失败");
    }
    setDeleteId(null);
  };

  const formatDate = (d: string) => {
    try {
      return format(new Date(d), "yyyy-MM-dd HH:mm", { locale: zhCN });
    } catch {
      return d;
    }
  };

  const envs = data?.items || [];
  const varCount = (env: Environment) =>
    env.variables ? Object.keys(env.variables).length : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">环境管理</h1>
        <Button onClick={openCreate} className="gap-2">
          <Plus className="h-4 w-4" />
          新建环境
        </Button>
      </div>

      {/* Loading / Error */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="overflow-hidden">
              <CardContent className="p-5">
                <div className="flex items-center gap-3 mb-4">
                  <Skeleton className="h-10 w-10 rounded-full" />
                  <div className="space-y-1.5">
                    <Skeleton className="h-4 w-24" />
                    <Skeleton className="h-3 w-16" />
                  </div>
                </div>
                <Skeleton className="h-4 w-full mb-2" />
                <Skeleton className="h-4 w-3/4 mb-3" />
                <div className="flex items-center gap-2">
                  <Skeleton className="h-5 w-16 rounded-full" />
                  <Skeleton className="h-4 w-20 ml-auto" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {isError && (
        <Card>
          <CardContent className="py-12 text-center text-destructive">
            加载失败，请检查后端服务。
          </CardContent>
        </Card>
      )}

      {/* Environment Cards Grid */}
      {!isLoading && !isError && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {envs.map((env: Environment) => (
            <Card
              key={env.id}
              className="group hover:shadow-md transition-shadow"
            >
              <CardContent className="pt-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className="h-8 w-8 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Globe className="h-4 w-4 text-primary" />
                    </div>
                    <div>
                      <h3 className="font-semibold">{env.name}</h3>
                      {env.description && (
                        <p className="text-xs text-muted-foreground line-clamp-1">
                          {env.description}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Button variant="ghost" size="icon" onClick={() => openEdit(env)}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => setDeleteId(env.id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground">Base URL:</span>
                    <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">
                      {env.base_url}
                    </code>
                  </div>
                  {env.ws_url && (
                    <div className="flex items-center gap-2">
                      <Wifi className="h-3 w-3 text-muted-foreground" />
                      <code className="text-xs text-muted-foreground font-mono">
                        {env.ws_url}
                      </code>
                    </div>
                  )}
                  <div className="flex items-center gap-2 pt-1">
                    <Badge variant="secondary" className="text-xs">
                      {varCount(env)} 个变量
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      创建于 {formatDate(env.created_at)}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          {envs.length === 0 && (
            <div className="col-span-full py-16 text-center text-muted-foreground">
              <p className="text-lg mb-1">暂无环境配置</p>
              <p className="text-sm">点击「新建环境」开始</p>
            </div>
          )}
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editingEnv ? "编辑环境" : "新建环境"}
            </DialogTitle>
            <DialogDescription>
              配置环境的基本信息和连接地址。
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit}>
            <div className="space-y-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="env-name">环境名称 *</Label>
                <Input
                  id="env-name"
                  value={formData.name}
                  onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
                  placeholder="dev / staging / production"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="env-desc">描述</Label>
                <Textarea
                  id="env-desc"
                  value={formData.description}
                  onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
                  placeholder="环境用途说明"
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="env-url">Base URL *</Label>
                <Input
                  id="env-url"
                  value={formData.base_url}
                  onChange={(e) => setFormData((p) => ({ ...p, base_url: e.target.value }))}
                  placeholder="https://api.example.com"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="env-ws">WebSocket URL</Label>
                <Input
                  id="env-ws"
                  value={formData.ws_url}
                  onChange={(e) => setFormData((p) => ({ ...p, ws_url: e.target.value }))}
                  placeholder="wss://ws.example.com"
                />
              </div>

              {/* Variables Editor */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>环境变量</Label>
                  <Button type="button" variant="outline" size="sm" onClick={addVariableRow}>
                    <Plus className="mr-1 h-3 w-3" />
                    添加变量
                  </Button>
                </div>
                <div className="space-y-2 rounded-lg border p-3">
                  {variables.map((v, idx) => (
                    <div key={idx} className="flex gap-2">
                      <Input
                        placeholder="KEY"
                        value={v.key}
                        onChange={(e) => updateVariableRow(idx, "key", e.target.value)}
                        className="flex-1 font-mono text-sm"
                      />
                      <Input
                        placeholder="VALUE"
                        value={v.value}
                        onChange={(e) => updateVariableRow(idx, "value", e.target.value)}
                        className="flex-[2] font-mono text-sm"
                      />
                      {variables.length > 1 && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          onClick={() => removeVariableRow(idx)}
                        >
                          <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                        </Button>
                      )}
                    </div>
                  ))}
                  {variables.length === 0 && (
                    <p className="text-xs text-muted-foreground text-center py-2">
                      暂无变量配置
                    </p>
                  )}
                </div>
              </div>
            </div>
            <DialogFooter className="mt-4">
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                取消
              </Button>
              <Button
                type="submit"
                disabled={createEnv.isPending || updateEnv.isPending}
              >
                {(createEnv.isPending || updateEnv.isPending) && (
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
              删除环境配置将同时清除关联的变量。此操作不可撤销。
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              disabled={deleteEnv.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteEnv.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              删除
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
