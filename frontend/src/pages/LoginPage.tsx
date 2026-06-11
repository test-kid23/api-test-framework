import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { login } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { FlaskConical, Loader2, AlertCircle } from "lucide-react";

export function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!username.trim() || !password.trim()) {
      setError(t("auth.emptyFieldsError"));
      return;
    }

    setLoading(true);
    try {
      const res = await login({ username: username.trim(), password });
      setAuth(res.token.access_token, res.token.refresh_token || "", res.user);
      navigate("/cases", { replace: true });
    } catch (err: unknown) {
      const respData = (err as { response?: { data?: Record<string, unknown> } }).response?.data;
      // FastAPI HTTPException 格式: { detail: { error, code } }
      const rawDetail = respData?.detail;
      let msg = t("auth.loginFailed");
      if (typeof rawDetail === "string") {
        msg = rawDetail;
      } else if (rawDetail && typeof rawDetail === "object") {
        const d = rawDetail as { error?: string; code?: string };
        msg = d.error || JSON.stringify(rawDetail);
      } else if (typeof respData?.error === "string") {
        msg = respData.error;
      }
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
          <CardTitle className="text-xl">{t("app.title")}</CardTitle>
          <CardDescription>{t("app.subtitle")}</CardDescription>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="flex items-start gap-2 rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="username" className="text-sm font-medium">
                {t("auth.username")}
              </label>
              <Input
                id="username"
                type="text"
                placeholder={t("auth.usernamePlaceholder")}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                disabled={loading}
                autoFocus
              />
            </div>

            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                {t("auth.password")}
              </label>
              <Input
                id="password"
                type="password"
                placeholder={t("auth.passwordPlaceholder")}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                disabled={loading}
              />
            </div>
          </CardContent>

          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  {t("auth.loggingIn")}
                </>
              ) : (
                t("auth.login")
              )}
            </Button>
            <p className="text-sm text-muted-foreground text-center">
              {t("app.noAccount")}{" "}
              <Link
                to="/register"
                className="text-primary hover:underline font-medium"
              >
                {t("app.goRegister")}
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
