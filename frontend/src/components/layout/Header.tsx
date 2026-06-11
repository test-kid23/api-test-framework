import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAppStore } from "@/store/appStore";
import { useAuthStore } from "@/store/authStore";
import { usePermission } from "@/hooks/usePermission";
import { ChangePasswordDialog } from "@/components/auth/ChangePasswordDialog";
import { LanguageSwitcher } from "@/components/LanguageSwitcher";
import { Menu, Search, ChevronDown, Settings, Sun, Moon, Monitor, LogOut, Key } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";

const quickLinks = [
  { label: "sidebar:caseManagement", to: "/cases", shortcut: "C" },
  { label: "sidebar:suiteManagement", to: "/suites", shortcut: "S" },
  { label: "sidebar:executionHistory", to: "/executions", shortcut: "E" },
  { label: "sidebar:dashboard", to: "/dashboard", shortcut: "D" },
  { label: "sidebar:environmentManagement", to: "/environments", shortcut: "V" },
  { label: "sidebar:scheduledTasks", to: "/schedules", shortcut: "T" },
];

const roleLabels: Record<string, string> = {
  admin: "管理员",
  editor: "编辑者",
  viewer: "观察者",
};

export function Header() {
  const { t } = useTranslation();
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const toggleMobileSidebar = useAppStore((s) => s.toggleMobileSidebar);
  const selectedEnv = useAppStore((s) => s.selectedEnv);
  const theme = useAppStore((s) => s.theme);
  const setTheme = useAppStore((s) => s.setTheme);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const { isAdmin } = usePermission();
  const navigate = useNavigate();
  const [cmdOpen, setCmdOpen] = useState(false);
  const [pwdDialogOpen, setPwdDialogOpen] = useState(false);

  const cycleTheme = () => {
    const next: Record<"light" | "dark" | "system", "light" | "dark" | "system"> = {
      light: "dark",
      dark: "system",
      system: "light",
    };
    setTheme(next[theme]);
  };

  const themeIcon = {
    light: Sun,
    dark: Moon,
    system: Monitor,
  }[theme];

  const ThemeIcon = themeIcon;

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  // ⌘K / Ctrl+K 唤起命令面板
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      setCmdOpen(true);
    }
  };

  const displayName = user?.username || "User";
  const roleLabel = roleLabels[user?.role || ""] || user?.role || "";
  const initial = displayName.charAt(0).toUpperCase();

  return (
    <>
      <header
        className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-card/80 backdrop-blur-sm px-4"
        onKeyDown={handleKeyDown}
      >
        <div className="flex items-center gap-3">
          {/* Mobile sidebar toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={toggleMobileSidebar}
          >
            <Menu className="h-5 w-5" />
          </Button>
          {/* Desktop sidebar toggle */}
          <Button
            variant="ghost"
            size="icon"
            className="hidden md:inline-flex"
            onClick={toggleSidebar}
          >
            <Menu className="h-5 w-5" />
          </Button>

          {/* ⌘K 搜索按钮 */}
          <Button
            variant="outline"
            size="sm"
            className="hidden md:inline-flex text-muted-foreground gap-2 h-8 px-3"
            onClick={() => setCmdOpen(true)}
          >
            <Search className="h-4 w-4" />
            <span className="text-xs">{t("common.search")}...</span>
            <kbd className="ml-8 pointer-events-none inline-flex h-5 select-none items-center gap-0.5 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
              ⌘K
            </kbd>
          </Button>
        </div>

        <div className="flex items-center gap-3">
          {/* Language Switcher */}
          <LanguageSwitcher />

          {/* Theme toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={cycleTheme}
            title={`${theme === "light" ? "Light" : theme === "dark" ? "Dark" : "System"}`}
          >
            <ThemeIcon className="h-4 w-4" />
          </Button>

          {/* Environment Switcher */}
          <Button
            variant="ghost"
            size="sm"
            className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground"
          >
            <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
            <span className="font-medium text-foreground">{selectedEnv}</span>
            <ChevronDown className="h-3 w-3" />
          </Button>

          {/* User Menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="sm" className="flex items-center gap-2">
                <Avatar className="h-7 w-7">
                  <AvatarFallback className="text-xs bg-primary/10 text-primary font-medium">
                    {initial}
                  </AvatarFallback>
                </Avatar>
                <span className="text-sm hidden md:inline">{displayName}</span>
                <ChevronDown className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuLabel>
                <div className="flex flex-col gap-0.5">
                  <span>{displayName}</span>
                  {roleLabel && (
                    <span className="text-xs font-normal text-muted-foreground">{roleLabel}</span>
                  )}
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => setPwdDialogOpen(true)}>
                <Key className="mr-2 h-4 w-4" />
                {t("auth.changePassword")}
              </DropdownMenuItem>
              {isAdmin && (
                <DropdownMenuItem onClick={() => navigate("/environments")}>
                  <Settings className="mr-2 h-4 w-4" />
                  {t("sidebar:systemSettings")}
                </DropdownMenuItem>
              )}
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
                <LogOut className="mr-2 h-4 w-4" />
                {t("auth.logout")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* ⌘K Command Dialog */}
      <CommandDialog open={cmdOpen} onOpenChange={setCmdOpen}>
        <CommandInput placeholder={t("sidebar:searchPages")} />
        <CommandList>
          <CommandEmpty>{t("common:noData")}</CommandEmpty>
          <CommandGroup heading={t("sidebar:systemSettings")}>
            {quickLinks.map((link) => (
              <CommandItem
                key={link.to}
                onSelect={() => {
                  navigate(link.to);
                  setCmdOpen(false);
                }}
              >
                {t(link.label)}
                <span className="ml-auto text-xs text-muted-foreground">
                  ⌘+{link.shortcut}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>

      {/* Change Password Dialog */}
      <ChangePasswordDialog
        open={pwdDialogOpen}
        onOpenChange={setPwdDialogOpen}
      />
    </>
  );
}
