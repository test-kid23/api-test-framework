import { createHashRouter, Navigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { CasesPage } from "@/pages/CasesPage";
import { CaseEditPage } from "@/pages/CaseEditPage";
import { CaseDetailPage } from "@/pages/CaseDetailPage";
import { CaseImportPage } from "@/pages/CaseImportPage";
import { ExecutionsPage } from "@/pages/ExecutionsPage";
import { ExecutionDetailPage } from "@/pages/ExecutionDetailPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { EnvironmentsPage } from "@/pages/EnvironmentsPage";
import { SuitesPage } from "@/pages/SuitesPage";
import { SchedulesPage } from "@/pages/SchedulesPage";
import { ReportsPage } from "@/pages/ReportsPage";

export const router = createHashRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Navigate to="/cases" replace /> },
      { path: "cases", element: <CasesPage /> },
      { path: "cases/new", element: <CaseEditPage /> },
      { path: "cases/import", element: <CaseImportPage /> },
      { path: "cases/:id/edit", element: <CaseEditPage /> },
      { path: "cases/:id", element: <CaseDetailPage /> },
      { path: "suites", element: <SuitesPage /> },
      { path: "executions", element: <ExecutionsPage /> },
      { path: "executions/:id", element: <ExecutionDetailPage /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "environments", element: <EnvironmentsPage /> },
      { path: "schedules", element: <SchedulesPage /> },
      { path: "reports", element: <ReportsPage /> },
    ],
  },
]);
