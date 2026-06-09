import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  FileText,
  Package,
  Play,
  BarChart3,
  Settings,
  Clock,
  Terminal,
  ChevronLeft,
  Server,
  Radio,
  Sparkles,
} from "lucide-react";
import { useAppStore } from "@/store/appStore";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";

interface NavGroup {
  label: string;
  items: {
    to: string;
    label: string;
    icon: React.ComponentType<{ className?: string }>;
  }[];
}

const navGroups: NavGroup[] = [
  {
    label: "测试管理",
    items: [
      { to: "/cases", label: "用例管理", icon: FileText },
      { to: "/suites", label: "套件管理", icon: Package },
      { to: "/executions", label: "执行历史", icon: Play },
    ],
  },
  {
    label: "数据分析",
    items: [
      { to: "/dashboard", label: "报告看板", icon: BarChart3 },
    ],
  },
  {
    label: "测试工具",
    items: [
      { to: "/mocks", label: "Mock 规则", icon: Server },
      { to: "/recorder", label: "流量录制", icon: Radio },
      { to: "/smart-assertions", label: "智能断言", icon: Sparkles },
    ],
  },
  {
    label: "系统设置",
    items: [
      { to: "/environments", label: "环境管理", icon: Settings },
      { to: "/schedules", label: "定时调度", icon: Clock },
    ],
  },
];

export function Sidebar() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 flex h-screen flex-col border-r bg-card transition-all duration-300",
        sidebarOpen ? "w-60" : "w-16"
      )}
    >
      {/* Mobile close button */}
      <div className="md:hidden absolute top-3 right-3 z-50">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleSidebar}
          className="h-7 w-7"
        >
          <ChevronLeft className="h-4 w-4" />
        </Button>
      </div>
      {/* Logo */}
      <div className="flex h-14 items-center border-b px-4">
        <Terminal className="h-6 w-6 text-primary flex-shrink-0" />
        {sidebarOpen && (
          <span className="ml-3 font-bold text-lg whitespace-nowrap">
            AutoTest
          </span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-4 overflow-y-auto p-2">
        {navGroups.map((group) => (
          <div key={group.label}>
            {sidebarOpen && (
              <h3 className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {group.label}
              </h3>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) =>
                sidebarOpen ? (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center rounded-md px-3 py-2 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-primary/10 text-primary"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                      )
                    }
                  >
                    <item.icon className="h-5 w-5 flex-shrink-0" />
                    <span className="ml-3">{item.label}</span>
                  </NavLink>
                ) : (
                  <Tooltip key={item.to} delayDuration={0}>
                    <TooltipTrigger asChild>
                      <NavLink
                        to={item.to}
                        className={({ isActive }) =>
                          cn(
                            "flex items-center justify-center rounded-md py-2 text-sm font-medium transition-colors",
                            isActive
                              ? "bg-primary/10 text-primary"
                              : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                          )
                        }
                      >
                        <item.icon className="h-5 w-5 flex-shrink-0" />
                      </NavLink>
                    </TooltipTrigger>
                    <TooltipContent side="right" className="ml-1">
                      {item.label}
                    </TooltipContent>
                  </Tooltip>
                )
              )}
            </div>
          </div>
        ))}
      </nav>

      <Separator />

      {/* Bottom: collapse toggle */}
      <div className="p-2">
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-center text-muted-foreground"
          onClick={toggleSidebar}
        >
          <ChevronLeft
            className={cn(
              "h-4 w-4 transition-transform",
              !sidebarOpen && "rotate-180"
            )}
          />
          {sidebarOpen && <span className="ml-2 text-xs">收起菜单</span>}
        </Button>
      </div>
    </aside>
  );
}
