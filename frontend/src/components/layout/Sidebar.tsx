import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  FileText,
  Play,
  BarChart3,
  Settings,
  Terminal,
} from "lucide-react";
import { useAppStore } from "@/store/appStore";

const navItems = [
  { to: "/cases", label: "用例管理", icon: FileText },
  { to: "/executions", label: "执行历史", icon: Play },
  { to: "/dashboard", label: "报告看板", icon: BarChart3 },
  { to: "/environments", label: "环境管理", icon: Settings },
];

export function Sidebar() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 h-screen border-r bg-card transition-all duration-300",
        sidebarOpen ? "w-60" : "w-16"
      )}
    >
      <div className="flex h-14 items-center border-b px-4">
        <Terminal className="h-6 w-6 text-primary flex-shrink-0" />
        {sidebarOpen && (
          <span className="ml-3 font-bold text-lg whitespace-nowrap">
            AutoTest
          </span>
        )}
      </div>
      <nav className="space-y-1 p-2">
        {navItems.map((item) => (
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
            {sidebarOpen && <span className="ml-3">{item.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
