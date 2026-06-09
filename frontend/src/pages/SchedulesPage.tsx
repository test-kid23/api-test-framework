import { useState } from "react";
import { Plus, Pencil, Trash2, Play, Loader2, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  useSchedules, useCreateSchedule, useUpdateSchedule, useDeleteSchedule, useRunSchedule,
} from "@/hooks/useSchedules";
import { useSuites } from "@/hooks/useSuites";
import { useEnvironments } from "@/hooks/useEnvironments";
import { toast } from "sonner";
import type { Schedule, ScheduleCreate, ScheduleTriggerType } from "@/types";

const cronPresets = [
  { label: "每小时", value: "0 * * * *" },
  { label: "每天 09:00", value: "0 9 * * *" },
  { label: "每天 18:00", value: "0 18 * * *" },
  { label: "每周一 09:00", value: "0 9 * * 1" },
];

function formatNextRun(dateStr: string | null): string {
  if (!dateStr) return "—";
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  if (diffMs < 0) return "已过期";
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 60) return `${diffMin} 分钟后`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} 小时后`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay} 天后 (${d.toLocaleDateString("zh-CN")})`;
}

export function SchedulesPage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingSchedule, setEditingSchedule] = useState<Schedule | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Schedule | null>(null);

  const { data, isLoading } = useSchedules({ page: 1, page_size: 100 });
  const { data: suitesData } = useSuites({ page: 1, page_size: 100 });
  const { data: envsData } = useEnvironments({ page: 1, page_size: 50 });
  const createSchedule = useCreateSchedule();
  const updateSchedule = useUpdateSchedule();
  const deleteSchedule = useDeleteSchedule();
  const runSchedule = useRunSchedule();

  const schedules = data?.items ?? [];
  const suites = suitesData?.items ?? [];
  const envs = envsData?.items ?? [];

  // Form state
  const [formName, setFormName] = useState("");
  const [formSuiteId, setFormSuiteId] = useState("");
  const [formEnv, setFormEnv] = useState("");
  const triggerType: ScheduleTriggerType = "cron";
  const [formCron, setFormCron] = useState("");
  const [formEnabled, setFormEnabled] = useState(true);

  function openCreate() {
    setEditingSchedule(null);
    setFormName("");
    setFormSuiteId("");
    setFormEnv("");
    setFormCron("");
    setFormEnabled(true);
    setDialogOpen(true);
  }

  function openEdit(s: Schedule) {
    setEditingSchedule(s);
    setFormName(s.name);
    setFormSuiteId(s.suite_id);
    setFormEnv(s.env_name || "");
    setFormCron(s.cron_expression || "");
    setFormEnabled(s.enabled);
    setDialogOpen(true);
  }

  async function handleSave() {
    if (!formName.trim() || !formSuiteId) {
      toast.error("请填写名称和选择套件");
      return;
    }
    try {
      if (editingSchedule) {
        await updateSchedule.mutateAsync({
          id: editingSchedule.id,
          payload: {
            name: formName.trim(),
            env_name: formEnv || undefined,
            cron_expression: formCron || null,
            enabled: formEnabled,
          },
        });
        toast.success("调度已更新");
      } else {
        const payload: ScheduleCreate = {
          name: formName.trim(),
          suite_id: formSuiteId,
          env_name: formEnv || undefined,
          trigger_type: triggerType,
          cron_expression: formCron || null,
          enabled: formEnabled,
        };
        await createSchedule.mutateAsync(payload);
        toast.success("调度已创建");
      }
      setDialogOpen(false);
    } catch {
      toast.error("保存失败");
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    try {
      await deleteSchedule.mutateAsync(deleteTarget.id);
      toast.success("调度已删除");
    } catch {
      toast.error("删除失败");
    }
  }

  async function handleRunNow(id: string) {
    try {
      await runSchedule.mutateAsync(id);
      toast.success("手动触发成功");
    } catch {
      toast.error("触发失败");
    }
  }

  async function handleToggleEnabled(s: Schedule) {
    try {
      await updateSchedule.mutateAsync({
        id: s.id,
        payload: { enabled: !s.enabled },
      });
      toast.success(s.enabled ? "已停用" : "已启用");
    } catch {
      toast.error("操作失败");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">定时调度</h1>
        <Button onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" />新建调度
        </Button>
      </div>

      {/* Schedule Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="p-6 space-y-0">
              <div className="flex items-center gap-4 pb-3 border-b">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 w-28 ml-auto" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-24" />
              </div>
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 py-3 border-b last:border-0">
                  <Skeleton className="h-4 w-36" />
                  <Skeleton className="h-5 w-16 rounded-full" />
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-4 w-32 ml-auto" />
                  <Skeleton className="h-5 w-9 rounded-full" />
                  <div className="flex gap-1">
                    <Skeleton className="h-7 w-7 rounded" />
                    <Skeleton className="h-7 w-7 rounded" />
                    <Skeleton className="h-7 w-7 rounded" />
                  </div>
                </div>
              ))}
            </div>
          ) : schedules.length === 0 ? (
            <div className="py-0">
              <EmptyState
                icon={Clock}
                title="暂无定时调度"
                description="创建定时调度，让测试自动在指定时间运行"
                action={{ label: "新建调度", onClick: openCreate }}
              />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称</TableHead>
                  <TableHead>套件</TableHead>
                  <TableHead>环境</TableHead>
                  <TableHead>Cron 表达式</TableHead>
                  <TableHead>下次运行</TableHead>
                  <TableHead>启用</TableHead>
                  <TableHead className="w-[120px]">操作</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {schedules.map((s) => {
                  const suite = suites.find((st) => st.id === s.suite_id);
                  return (
                    <TableRow key={s.id}>
                      <TableCell className="font-medium">{s.name}</TableCell>
                      <TableCell>
                        {suite?.name ? (
                          <Badge variant="secondary">{suite.name}</Badge>
                        ) : (
                          <span className="text-muted-foreground text-sm">{s.suite_id}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <span className="text-sm text-muted-foreground">
                          {s.env_name || "—"}
                        </span>
                      </TableCell>
                      <TableCell>
                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded">
                          {s.cron_expression || "—"}
                        </code>
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatNextRun(s.next_run_at)}
                      </TableCell>
                      <TableCell>
                        <Switch
                          checked={s.enabled}
                          onCheckedChange={() => handleToggleEnabled(s)}
                          disabled={updateSchedule.isPending}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleRunNow(s.id)}
                            disabled={runSchedule.isPending}
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEdit(s)}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeleteTarget(s)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Create / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{editingSchedule ? "编辑调度" : "新建调度"}</DialogTitle>
            <DialogDescription>
              配置定时执行策略，支持 Cron 表达式
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="sched-name">名称 *</Label>
                <Input
                  id="sched-name"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="每日冒烟测试"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="sched-env">环境</Label>
                <Select value={formEnv} onValueChange={setFormEnv}>
                  <SelectTrigger id="sched-env">
                    <SelectValue placeholder="默认环境" />
                  </SelectTrigger>
                  <SelectContent>
                    {envs.map((env) => (
                      <SelectItem key={env.id} value={env.name}>
                        {env.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="sched-suite">目标套件 *</Label>
              <Select value={formSuiteId} onValueChange={setFormSuiteId}>
                <SelectTrigger id="sched-suite">
                  <SelectValue placeholder="选择套件" />
                </SelectTrigger>
                <SelectContent>
                  {suites.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="sched-cron">Cron 表达式</Label>
              <Input
                id="sched-cron"
                value={formCron}
                onChange={(e) => setFormCron(e.target.value)}
                placeholder="0 9 * * *"
                className="font-mono"
              />
              <div className="flex flex-wrap gap-1.5 pt-1">
                {cronPresets.map((p) => (
                  <Button
                    key={p.value}
                    variant={formCron === p.value ? "default" : "outline"}
                    size="sm"
                    className="text-xs h-7"
                    onClick={() => setFormCron(p.value)}
                  >
                    {p.label}
                  </Button>
                ))}
              </div>
            </div>
            <Separator />
            <div className="flex items-center justify-between rounded-lg border p-3">
              <div>
                <Label className="text-sm">启用调度</Label>
                <p className="text-xs text-muted-foreground">
                  停用后调度将暂停执行
                </p>
              </div>
              <Switch
                checked={formEnabled}
                onCheckedChange={setFormEnabled}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              取消
            </Button>
            <Button
              onClick={handleSave}
              disabled={createSchedule.isPending || updateSchedule.isPending}
            >
              {(createSchedule.isPending || updateSchedule.isPending) && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirm */}
      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>确认删除</AlertDialogTitle>
            <AlertDialogDescription>
              确定要删除调度「{deleteTarget?.name}」吗？
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>取消</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {deleteSchedule.isPending && (
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
