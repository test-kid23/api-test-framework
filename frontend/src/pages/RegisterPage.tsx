import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FlaskConical, Loader2, AlertCircle, CheckCircle } from "lucide-react";

export function RegisterPage() {
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState("viewer");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!username.trim()) {
      setError("请输入用户名");
      return;
    }
    if (username.trim().length < 3) {
      setError("用户名至少需要 3 个字符");
      return;
    }
    if (!password) {
      setError("请输入密码");
      return;
    }
    if (password.length < 6) {
      setError("密码至少需要 6 个字符");
      return;
    }
    if (password !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }

    setLoading(true);
    try {
      await register({ username: username.trim(), password, role });
      setSuccess("注册成功！即将跳转到登录页...");
      setTimeout(() => {
        navigate("/login", { replace: true });
      }, 1500);
    } catch (err: unknown) {
      const detail = (
        err as { response?: { data?: { error?: string; detail?: string } } }
      ).response?.data;
      const msg =
        typeof detail === "string"
          ? detail
          : detail?.error || detail?.detail || "注册失败，请重试";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/40">
      <Card className="w-full max-w-sm shadow-lg">
        <CardHeader className="text-center pb-4">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
            <FlaskConical className="h-6 w-6 text-primary" />
          </div>
          <CardTitle className="text-xl">创建账号</CardTitle>
          <CardDescription>注册一个新的 AutoTest 账号</CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {success && (
              <div className="flex items-start gap-2 rounded-md border border-emerald-500/50 bg-emerald-50 dark:bg-emerald-950/30 p-3 text-sm text-emerald-700 dark:text-emerald-400">
                <CheckCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{success}</span>
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="username" className="text-sm font-medium">
                用户名
              </label>
              <Input
                id="username"
                type="text"
                placeholder="3-128 位字母、数字或下划线"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                disabled={loading}
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                密码
              </label>
              <Input
                id="password"
                type="password"
                placeholder="至少 6 个字符"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                disabled={loading}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="confirmPassword" className="text-sm font-medium">
                确认密码
              </label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="再次输入密码"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                disabled={loading}
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="role" className="text-sm font-medium">
                角色
              </label>
              <Select value={role} onValueChange={setRole} disabled={loading}>
                <SelectTrigger id="role">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="viewer">观察者 — 只读访问</SelectItem>
                  <SelectItem value="editor">编辑者 — 可创建和编辑</SelectItem>
                  <SelectItem value="admin">管理员 — 全部权限</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                管理员创建后仍需管理员手动激活
              </p>
            </div>
          </CardContent>

          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  注册中...
                </>
              ) : (
                "注 册"
              )}
            </Button>
            <p className="text-sm text-muted-foreground text-center">
              已有账号？{" "}
              <Link
                to="/login"
                className="text-primary hover:underline font-medium"
              >
                去登录
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
