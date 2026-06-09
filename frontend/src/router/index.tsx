import { createHashRouter, Navigate } from "react-router-dom";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { AppLayout } from "@/components/layout/AppLayout";
import { LoginPage } from "@/pages/LoginPage";
import { RegisterPage } from "@/pages/RegisterPage";
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
import { MockRulesPage } from "@/pages/MockRulesPage";
import { RecorderPage } from "@/pages/RecorderPage";
import { SmartAssertionPage } from "@/pages/SmartAssertionPage";
import { CoveragePage } from "@/pages/CoveragePage";
import { UsersPage } from "@/pages/UsersPage";
import { RoleGuard } from "@/components/auth/RoleGuard";

export const router = createHashRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },
  {
    path: "/register",
    element: <RegisterPage />,
  },
  {
    path: "/",
    element: (
      <AuthGuard>
        <AppLayout />
      </AuthGuard>
    ),
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
      { path: "mocks", element: <MockRulesPage /> },
      { path: "recorder", element: <RecorderPage /> },
      { path: "smart-assertions", element: <SmartAssertionPage /> },
      { path: "coverage", element: <CoveragePage /> },
      {
        path: "users",
        element: (
          <RoleGuard roles={["admin"]}>
            <UsersPage />
          </RoleGuard>
        ),
      },
    ],
  },
]);
