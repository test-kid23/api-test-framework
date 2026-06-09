// ============================================================
// AutoTest Framework · Frontend Type Definitions
// 对齐后端 api/schemas/ 下的 Pydantic Schema
// ============================================================

// ── Common / Pagination ─────────────────────────────────────

export interface PaginationMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  pagination: PaginationMeta;
}

// ── TestCase ─────────────────────────────────────────────────

export type CasePriority = "P0" | "P1" | "P2" | "P3";

export interface TestCase {
  id: string;
  name: string;
  description: string;
  tags: string[];
  priority: CasePriority;
  yaml_content: string;
  timeout: number | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TestCaseListItem {
  id: string;
  name: string;
  description: string;
  tags: string[];
  priority: CasePriority;
  timeout: number | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface TestCaseCreate {
  name: string;
  description?: string;
  tags?: string[];
  priority?: CasePriority;
  yaml_content: string;
  timeout?: number | null;
}

export interface TestCaseUpdate {
  name?: string;
  description?: string;
  tags?: string[];
  priority?: CasePriority;
  yaml_content?: string;
  timeout?: number | null;
}

export interface CaseImportRequest {
  spec_url: string;
  suite_name?: string;
}

export interface CaseImportResult {
  total_discovered: number;
  total_imported: number;
  total_skipped: number;
  suite_name: string;
  case_ids: string[];
  errors: string[];
}

// ── Execution ────────────────────────────────────────────────

export type ExecutionStatus =
  | "PENDING"
  | "RUNNING"
  | "PASSED"
  | "FAILED"
  | "ERROR"
  | "CANCELLED";

export type ExecutionTrigger = "manual" | "scheduled" | "webhook" | "api";

export interface ExecutionSummary {
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  error_cases: number;
}

export interface CaseResult {
  case_id: string;
  case_name: string;
  status: string; // "PASS" | "FAIL" | "SKIP" | "ERROR"
  error: string | null;
  elapsed_ms: number;
}

export interface Execution {
  id: string;
  name: string;
  status: ExecutionStatus;
  trigger: ExecutionTrigger;
  env: string;
  mode: string;
  celery_task_id: string | null;
  case_ids: string[];
  suite_id: string | null;
  results: CaseResult[];
  summary: ExecutionSummary;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExecutionRequest {
  case_ids: string[];
  suite_id?: string;
  env?: string;
  trigger?: ExecutionTrigger;
}

export interface ExecutionReport {
  execution_id: string;
  status: ExecutionStatus;
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  error: number;
  pass_rate: number;
  avg_elapsed_ms: number;
  results: CaseResult[];
  created_at: string | null;
  finished_at: string | null;
}

// ── Report ───────────────────────────────────────────────────

export interface TrendItem {
  date: string;
  total: number;
  passed: number;
  failed: number;
  pass_rate: number;
  avg_elapsed_ms: number;
}

export interface TrendResponse {
  days: number;
  items: TrendItem[];
}

export interface TopFailure {
  case_id: string;
  case_name: string;
  fail_count: number;
  last_failed_at: string | null;
  last_error: string | null;
}

export interface TopFailuresResponse {
  items: TopFailure[];
}

export interface ReportListItem {
  id: string;
  execution_id: string;
  execution_name: string;
  status: string;
  total_cases: number;
  passed: number;
  failed: number;
  pass_rate: number;
  env: string;
  created_at: string | null;
}

// Dashboard 聚合数据（由前端合并 trends + top-failures）
export interface DashboardData {
  pass_rate_trend: { date: string; rate: number }[];
  failure_categories: { category: string; count: number }[];
  top_unstable: { case_name: string; failure_count: number }[];
}

// ── Suite ────────────────────────────────────────────────────

export interface Suite {
  id: string;
  name: string;
  description: string;
  tags?: string[];
  config?: Record<string, unknown>;
  case_ids?: string[];
  created_at: string;
  updated_at: string;
}

export interface SuiteCreate {
  name: string;
  description?: string;
  tags?: string[];
  config?: Record<string, unknown>;
  case_ids?: string[];
}

export interface SuiteUpdate {
  name?: string;
  description?: string;
  tags?: string[];
  config?: Record<string, unknown>;
  case_ids?: string[];
}

// ── Schedule ─────────────────────────────────────────────────

export type ScheduleTriggerType = "cron" | "interval";

export interface Schedule {
  id: string;
  name: string;
  suite_id: string;
  env_name: string;
  trigger_type: ScheduleTriggerType;
  cron_expression: string | null;
  interval_seconds: number | null;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ScheduleCreate {
  name: string;
  suite_id: string;
  env_name?: string;
  trigger_type: ScheduleTriggerType;
  cron_expression?: string | null;
  interval_seconds?: number | null;
  enabled?: boolean;
}

export interface ScheduleUpdate {
  name?: string;
  env_name?: string;
  enabled?: boolean;
  cron_expression?: string | null;
  interval_seconds?: number | null;
}

// ── Environment ──────────────────────────────────────────────

export interface Environment {
  id: string;
  name: string;
  description: string | null;
  base_url: string | null;
  ws_url: string | null;
  variables: Record<string, string> | null;
  http_config: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface EnvironmentCreate {
  name: string;
  description?: string | null;
  base_url?: string | null;
  ws_url?: string | null;
  variables?: Record<string, string> | null;
  http_config?: Record<string, unknown> | null;
}

export interface EnvironmentUpdate {
  name?: string | null;
  description?: string | null;
  base_url?: string | null;
  ws_url?: string | null;
  variables?: Record<string, string> | null;
  http_config?: Record<string, unknown> | null;
}
