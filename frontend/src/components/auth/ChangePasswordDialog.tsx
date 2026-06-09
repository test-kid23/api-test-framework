import { useState } from "react";
import { changePassword } from "@/api/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Loader2, AlertCircle, CheckCircle } from "lucide-react";

interface ChangePasswordDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ChangePasswordDialog({
  open,
  onOpenChange,
}: ChangePasswordDialogProps) {
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const reset = () => {
    setOldPassword("");
    setNewPassword("");
    setConfirmNewPassword("");
    setError("");
    setSuccess("");
  };

  const handleOpenChange = (open: boolean) => {
    if (!open) reset();
    onOpenChange(open);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!oldPassword) {
      setError("请输入当前密码");
      return;
    }
    if (!newPassword) {
      setError("请输入新密码");
      return;
    }
    if (newPassword.length < 6) {
      setError("新密码至少需要 6 个字符");
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setError("两次输入的新密码不一致");
      return;
    }

    setLoading(true);
    try {
      await changePassword({
        old_password: oldPassword,
        new_password: newPassword,
      });
      setSuccess("密码修改成功！");
      setTimeout(() => {
        handleOpenChange(false);
      }, 1500);
    } catch (err: unknown) {
      const detail = (
        err as { response?: { data?: { error?: string; detail?: string } } }
      ).response?.data;
      const msg =
        typeof detail === "string"
          ? detail
          : detail?.error || detail?.detail || "修改密码失败，请重试";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>修改密码</DialogTitle>
          <DialogDescription>
            请输入当前密码和新密码。新密码至少 6 个字符。
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
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
            <label htmlFor="old-password" className="text-sm font-medium">
              当前密码
            </label>
            <Input
              id="old-password"
              type="password"
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              autoComplete="current-password"
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="new-password" className="text-sm font-medium">
              新密码
            </label>
            <Input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="confirm-new-password" className="text-sm font-medium">
              确认新密码
            </label>
            <Input
              id="confirm-new-password"
              type="password"
              value={confirmNewPassword}
              onChange={(e) => setConfirmNewPassword(e.target.value)}
              autoComplete="new-password"
              disabled={loading}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
              disabled={loading}
            >
              取消
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  修改中...
                </>
              ) : (
                "确认修改"
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
