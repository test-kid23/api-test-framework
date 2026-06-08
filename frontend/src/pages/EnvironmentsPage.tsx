import { useState } from "react";
import { useEnvironments, useCreateEnvironment, useDeleteEnvironment, useUpdateEnvironment } from "@/hooks/useEnvironments";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Plus, Pencil, Trash2, Loader2, Globe } from "lucide-react";
import type { Environment } from "@/types";

export function EnvironmentsPage() {
  const [page] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingEnv, setEditingEnv] = useState<Environment | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    base_url: "",
    ws_url: "",
  });

  const { data, isLoading, isError } = useEnvironments({ page, page_size: 20 });
  const createEnv = useCreateEnvironment();
  const updateEnv = useUpdateEnvironment();
  const deleteEnv = useDeleteEnvironment();

  const openCreate = () => {
    setEditingEnv(null);
    setFormData({ name: "", description: "", base_url: "", ws_url: "" });
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
    setDialogOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingEnv) {
        await updateEnv.mutateAsync({ id: editingEnv.id, payload: formData });
      } else {
        await createEnv.mutateAsync(formData);
      }
      setDialogOpen(false);
    } catch {
      // handled by query
    }
  };

  const handleDelete = async () => {
    if (!deleteId) return;
    await deleteEnv.mutateAsync(deleteId);
    setDeleteId(null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">环境管理</h1>
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" />
          新建环境
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : isError ? (
            <div className="p-6 text-center text-destructive">
              加载失败，请检查后端服务。
            </div>
          ) : data && data.items.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>环境名称</TableHead>
                  <TableHead>描述</TableHead>
                  <TableHead>Base URL</TableHead>
                  <TableHead className="w-[80px]">变量数</TableHead>
                  <TableHead className="w-[120px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.items.map((env) => (
                  <TableRow key={env.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <Globe className="h-4 w-4 text-muted-foreground" />
                        {env.name}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {env.description || "-"}
                    </TableCell>
                    <TableCell className="font-mono text-sm text-muted-foreground">
                      {env.base_url}
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{env.variable_count}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => openEdit(env)}
                        >
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
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-12 text-center text-muted-foreground">
              暂无环境配置，点击"新建环境"开始配置。
            </div>
          )}
        </CardContent>
      </Card>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {editingEnv ? "编辑环境" : "新建环境"}
            </DialogTitle>
            <DialogDescription>
              配置环境的基本信息和连接地址。
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="env-name">环境名称 *</Label>
                <Input
                  id="env-name"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData((p) => ({ ...p, name: e.target.value }))
                  }
                  placeholder="dev / staging / production"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="env-desc">描述</Label>
                <Textarea
                  id="env-desc"
                  value={formData.description}
                  onChange={(e) =>
                    setFormData((p) => ({ ...p, description: e.target.value }))
                  }
                  placeholder="环境用途说明"
                  rows={2}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="env-url">Base URL *</Label>
                <Input
                  id="env-url"
                  value={formData.base_url}
                  onChange={(e) =>
                    setFormData((p) => ({ ...p, base_url: e.target.value }))
                  }
                  placeholder="https://api.example.com"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="env-ws">WebSocket URL</Label>
                <Input
                  id="env-ws"
                  value={formData.ws_url}
                  onChange={(e) =>
                    setFormData((p) => ({ ...p, ws_url: e.target.value }))
                  }
                  placeholder="wss://ws.example.com"
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setDialogOpen(false)}
              >
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

      {/* Delete Confirmation Dialog */}
      <Dialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除</DialogTitle>
            <DialogDescription>
              删除环境配置将同时清除关联的变量。此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteEnv.isPending}
            >
              {deleteEnv.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
