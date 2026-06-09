import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAppStore } from "@/store/appStore";
import { Menu, Search, ChevronDown, Settings, Sun, Moon, Monitor } from "lucide-react";
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
  { label: "用例管理", to: "/cases", shortcut: "C" },
  { label: "套件管理", to: "/suites", shortcut: "S" },
  { label: "执行历史", to: "/executions", shortcut: "E" },
  { label: "报告看板", to: "/dashboard", shortcut: "D" },
  { label: "环境管理", to: "/environments", shortcut: "V" },
  { label: "定时调度", to: "/schedules", shortcut: "T" },
];

export function Header() {
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const toggleMobileSidebar = useAppStore((s) => s.toggleMobileSidebar);
  const currentUser = useAppStore((s) => s.currentUser);
  const selectedEnv = useAppStore((s) => s.selectedEnv);
  const theme = useAppStore((s) => s.theme);
  const setTheme = useAppStore((s) => s.setTheme);
  const navigate = useNavigate();
  const [cmdOpen, setCmdOpen] = useState(false);

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

  // ⌘K / Ctrl+K 唤起命令面板
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "k") {
      e.preventDefault();
      setCmdOpen(true);
    }
  };

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
            <span className="text-xs">搜索...</span>
            <kbd className="ml-8 pointer-events-none inline-flex h-5 select-none items-center gap-0.5 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground">
              ⌘K
            </kbd>
          </Button>
        </div>

        <div className="flex items-center gap-3">
          {/* Theme toggle */}
          <Button
            variant="ghost"
            size="icon"
            onClick={cycleTheme}
            title={`当前: ${theme === "light" ? "浅色" : theme === "dark" ? "深色" : "跟随系统"}`}
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
                    {currentUser.name.charAt(0)}
                  </AvatarFallback>
                </Avatar>
                <span className="text-sm hidden md:inline">{currentUser.name}</span>
                <ChevronDown className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuLabel>账户</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => navigate("/environments")}>
                <Settings className="mr-2 h-4 w-4" />
                系统设置
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* ⌘K Command Dialog */}
      <CommandDialog open={cmdOpen} onOpenChange={setCmdOpen}>
        <CommandInput placeholder="搜索页面..." />
        <CommandList>
          <CommandEmpty>未找到结果。</CommandEmpty>
          <CommandGroup heading="导航">
            {quickLinks.map((link) => (
              <CommandItem
                key={link.to}
                onSelect={() => {
                  navigate(link.to);
                  setCmdOpen(false);
                }}
              >
                {link.label}
                <span className="ml-auto text-xs text-muted-foreground">
                  快捷键 ⌘+{link.shortcut}
                </span>
              </CommandItem>
            ))}
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
