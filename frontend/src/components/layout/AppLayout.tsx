import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { useAppStore } from "@/store/appStore";
import { cn } from "@/lib/utils";
import { Sheet, SheetContent } from "@/components/ui/sheet";

export function AppLayout() {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const mobileSidebarOpen = useAppStore((s) => s.mobileSidebarOpen);
  const toggleMobileSidebar = useAppStore((s) => s.toggleMobileSidebar);
  const location = useLocation();

  // Close mobile sidebar on route change
  useEffect(() => {
    if (mobileSidebarOpen) toggleMobileSidebar();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-background">
      {/* Desktop Sidebar */}
      <div className="hidden md:block">
        <Sidebar />
      </div>

      {/* Mobile Sidebar (Sheet) */}
      <Sheet open={mobileSidebarOpen} onOpenChange={toggleMobileSidebar}>
        <SheetContent side="left" className="w-60 p-0">
          <Sidebar />
        </SheetContent>
      </Sheet>

      <div
        className={cn(
          "transition-all duration-300",
          sidebarOpen ? "md:ml-60" : "md:ml-16",
        )}
      >
        <Header />
        <main className="p-4 md:p-6 animate-page-enter">
          <Outlet />
        </main>
      </div>
      <Toaster richColors position="top-right" />
    </div>
  );
}
