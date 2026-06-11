import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
  Users,
  Target,
} from "lucide-react";
import { useAppStore } from "@/store/appStore";
import { useAuthStore } from "@/store/authStore";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";

interface NavGroup {
  labelKey: string;
  items: {
    to: string;
    labelKey: string;
    icon: React.ComponentType<{ className?: string }>;
    adminOnly?: boolean;
  }[];
}

const navGroups: NavGroup[] = [
  {
    labelKey: "sidebar:testManagement",
    items: [
      { to: "/cases", labelKey: "sidebar:caseManagement", icon: FileText },
      { to: "/suites", labelKey: "sidebar:suiteManagement", icon: Package },
      { to: "/executions", labelKey: "sidebar:executionHistory", icon: Play },
    ],
  },
  {
    labelKey: "sidebar:dataAnalysis",
    items: [
      { to: "/dashboard", labelKey: "sidebar:dashboard", icon: BarChart3 },
      { to: "/coverage", labelKey: "sidebar:coverageAnalysis", icon: Target },
    ],
  },
  {
    labelKey: "sidebar:testTools",
    items: [
      { to: "/mocks", labelKey: "sidebar:mockRules", icon: Server },
      { to: "/recorder", labelKey: "sidebar:trafficRecorder", icon: Radio },
      { to: "/smart-assertions", labelKey: "sidebar:smartAssertions", icon: Sparkles },
    ],
  },
  {
    labelKey: "sidebar:systemSettings",
    items: [
      { to: "/environments", labelKey: "sidebar:environmentManagement", icon: Settings },
      { to: "/schedules", labelKey: "sidebar:scheduledTasks", icon: Clock },
    ],
  },
  {
    labelKey: "sidebar:permissionManagement",
    items: [
      { to: "/users", labelKey: "sidebar:userManagement", icon: Users, adminOnly: true },
    ],
  },
];

export function Sidebar() {
  const { t } = useTranslation();
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const currentUser = useAuthStore((s) => s.user);
  const isAdmin = currentUser?.role === "admin";

  // 过滤掉非 admin 用户的 adminOnly 项
  const visibleGroups = navGroups
    .map((g) => ({
      ...g,
      items: g.items.filter((i) => !i.adminOnly || isAdmin),
    }))
    .filter((g) => g.items.length > 0);

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
        {visibleGroups.map((group) => (
          <div key={group.labelKey}>
            {sidebarOpen && (
              <h3 className="mb-1 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                {t(group.labelKey)}
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
                    <span className="ml-3">{t(item.labelKey)}</span>
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
                      {t(item.labelKey)}
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
          {sidebarOpen && <span className="ml-2 text-xs">{t("sidebar:collapse")}</span>}
        </Button>
      </div>
    </aside>
  );
}
