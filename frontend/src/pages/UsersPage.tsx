import { useEffect, useState } from "react";
import { useAuthStore } from "@/store/authStore";
import {
  createUser,
  deleteUser,
  listUsers,
  updateUser,
  type AdminCreateUserRequest,
  type AdminUpdateUserRequest,
} from "@/api/users";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  AlertCircle,
  Loader2,
  Plus,
  Search,
  Shield,
  Trash2,
  UserCog,
  Users as UsersIcon,
} from "lucide-react";
import type { AuthUser } from "@/store/authStore";

const ROLE_LABELS: Record<string, string> = {
  admin: "管理员",
  editor: "编辑者",
  viewer: "观察者",
};

const ROLE_VARIANT: Record<
  string,
  "default" | "secondary" | "destructive" | "outline"
> = {
  admin: "destructive",
  editor: "default",
  viewer: "secondary",
};

interface EditFormState {
  role: "admin" | "editor" | "viewer";
  is_active: boolean;
  new_password: string;
}

export function UsersPage() {
  const currentUser = useAuthStore((s) => s.user);

  const [users, setUsers] = useState<AuthUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 新建用户对话框
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<AdminCreateUserRequest>({
    username: "",
    password: "",
    role: "viewer",
    is_active: true,
  });

  // 编辑用户对话框
  const [editing, setEditing] = useState<AuthUser | null>(null);
  const [editForm, setEditForm] = useState<EditFormState>({
    role: "viewer",
    is_active: true,
    new_password: "",
  });

  const fetchUsers = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await listUsers(page, pageSize, search || undefined);
      setUsers(res.items);
      setTotal(res.pagination.total);
    } catch (err) {
      const msg =
        (err as { response?: { data?: { detail?: { error?: string } } } })
          .response?.data?.detail?.error || "加载用户列表失败";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page]);

  const handleSearch = () => {
    setPage(1);
    fetchUsers();
  };

  const handleCreate = async () => {
    setError("");
    try {
      await createUser(createForm);
      setCreateOpen(false);
      setCreateForm({
        username: "",
        password: "",
        role: "viewer",
        is_active: true,
      });
      fetchUsers();
    } catch (err) {
      const msg =
        (err as { response?: { data?: { detail?: { error?: string } } } })
          .response?.data?.detail?.error || "创建用户失败";
      setError(msg);
    }
  };

  const openEdit = (user: AuthUser) => {
    setEditing(user);
    setEditForm({
      role: user.role as "admin" | "editor" | "viewer",
      is_active: user.is_active,
      new_password: "",
    });
  };

  const handleUpdate = async () => {
    if (!editing) return;
    setError("");
    const payload: AdminUpdateUserRequest = {
      role: editForm.role,
      is_active: editForm.is_active,
    };
    if (editForm.new_password) {
      payload.new_password = editForm.new_password;
    }
    try {
      await updateUser(editing.id, payload);
      setEditing(null);
      fetchUsers();
    } catch (err) {
      const msg =
        (err as { response?: { data?: { detail?: { error?: string } } } })
          .response?.data?.detail?.error || "更新用户失败";
      setError(msg);
    }
  };

  const handleDelete = async (user: AuthUser) => {
    if (!confirm(`确认删除用户「${user.username}」？此操作不可恢复。`)) return;
    setError("");
    try {
      await deleteUser(user.id);
      fetchUsers();
    } catch (err) {
      const msg =
        (err as { response?: { data?: { detail?: { error?: string } } } })
          .response?.data?.detail?.error || "删除用户失败";
      setError(msg);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <UsersIcon className="h-5 w-5" />
                用户管理
              </CardTitle>
              <CardDescription>
                管理平台用户、角色与账号状态（仅管理员可见）
              </CardDescription>
            </div>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              创建用户
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* 搜索栏 */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="按用户名搜索..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="pl-8"
              />
            </div>
            <Button variant="outline" onClick={handleSearch}>
              搜索
            </Button>
          </div>

          {error && (
            <div className="flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>用户名</TableHead>
                    <TableHead>角色</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead>创建时间</TableHead>
                    <TableHead className="text-right">操作</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {users.length === 0 ? (
                    <TableRow>
                      <TableCell
                        colSpan={5}
                        className="text-center text-muted-foreground py-8"
                      >
                        暂无用户
                      </TableCell>
                    </TableRow>
                  ) : (
                    users.map((u) => (
                      <TableRow key={u.id}>
                        <TableCell className="font-medium">
                          {u.username}
                          {currentUser?.id === u.id && (
                            <Badge variant="outline" className="ml-2">
                              你
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant={ROLE_VARIANT[u.role] || "outline"}>
                            <Shield className="mr-1 h-3 w-3" />
                            {ROLE_LABELS[u.role] || u.role}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {u.is_active ? (
                            <Badge variant="default">启用</Badge>
                          ) : (
                            <Badge variant="secondary">已停用</Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {new Date(u.created_at).toLocaleString("zh-CN")}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => openEdit(u)}
                            >
                              <UserCog className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDelete(u)}
                              disabled={currentUser?.id === u.id}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>

              {/* 分页 */}
              <div className="flex items-center justify-between text-sm text-muted-foreground">
                <span>共 {total} 个用户</span>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    上一页
                  </Button>
                  <span>
                    第 {page} / {totalPages} 页
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    下一页
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* 创建用户对话框 */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>创建新用户</DialogTitle>
            <DialogDescription>
              为团队成员创建账号，可指定角色。系统会自动创建同名个人项目。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="cu-username">用户名</Label>
              <Input
                id="cu-username"
                value={createForm.username}
                onChange={(e) =>
                  setCreateForm({ ...createForm, username: e.target.value })
                }
                placeholder="字母/数字/下划线/连字符，3-128 字符"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cu-password">初始密码</Label>
              <Input
                id="cu-password"
                type="password"
                value={createForm.password}
                onChange={(e) =>
                  setCreateForm({ ...createForm, password: e.target.value })
                }
                placeholder="至少 6 字符"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="cu-role">角色</Label>
              <Select
                value={createForm.role}
                onValueChange={(v) =>
                  setCreateForm({
                    ...createForm,
                    role: v as "admin" | "editor" | "viewer",
                  })
                }
              >
                <SelectTrigger id="cu-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">观察者（只读）</SelectItem>
                  <SelectItem value="editor">编辑者（可写）</SelectItem>
                  <SelectItem value="admin">管理员（全部权限）</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="cu-active">启用账号</Label>
              <Switch
                id="cu-active"
                checked={createForm.is_active}
                onCheckedChange={(v) =>
                  setCreateForm({ ...createForm, is_active: v })
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              取消
            </Button>
            <Button
              onClick={handleCreate}
              disabled={!createForm.username || !createForm.password}
            >
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 编辑用户对话框 */}
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑用户：{editing?.username}</DialogTitle>
            <DialogDescription>
              调整角色、启用状态或重置密码（任一字段可选）
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="ed-role">角色</Label>
              <Select
                value={editForm.role}
                onValueChange={(v) =>
                  setEditForm({
                    ...editForm,
                    role: v as "admin" | "editor" | "viewer",
                  })
                }
              >
                <SelectTrigger id="ed-role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">观察者</SelectItem>
                  <SelectItem value="editor">编辑者</SelectItem>
                  <SelectItem value="admin">管理员</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="ed-active">启用账号</Label>
              <Switch
                id="ed-active"
                checked={editForm.is_active}
                onCheckedChange={(v) => setEditForm({ ...editForm, is_active: v })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="ed-pwd">重置密码（留空则不修改）</Label>
              <Input
                id="ed-pwd"
                type="password"
                value={editForm.new_password}
                onChange={(e) =>
                  setEditForm({ ...editForm, new_password: e.target.value })
                }
                placeholder="至少 6 字符"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>
              取消
            </Button>
            <Button onClick={handleUpdate}>保存</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
