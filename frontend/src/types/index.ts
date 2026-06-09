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

// ── Mock ──────────────────────────────────────────────────────

export interface MockRule {
  id: string;
  url_pattern: string;
  method: string;
  status_code: number;
  response_body: unknown;
  response_headers: Record<string, string>;
  description: string;
  enabled: boolean;
  priority: number;
  delay_ms: number;
}

export interface MockRuleCreate {
  url_pattern: string;
  method?: string;
  status_code?: number;
  response_body?: unknown;
  response_headers?: Record<string, string>;
  description?: string;
  priority?: number;
  delay_ms?: number;
}

export interface MockRuleUpdate {
  url_pattern?: string;
  method?: string;
  status_code?: number;
  response_body?: unknown;
  response_headers?: Record<string, string>;
  description?: string;
  enabled?: boolean;
  priority?: number;
  delay_ms?: number;
}

export interface MockRulesList {
  total: number;
  rules: MockRule[];
}

export interface MockBatchCreate {
  rules: MockRuleCreate[];
}

// ── Recorder ──────────────────────────────────────────────────

export type RecorderState = "idle" | "recording" | "paused";

export interface RecordingSession {
  session_id: string;
  name: string;
  state: RecorderState;
  started_at: string;
  stopped_at: string;
  entry_count: number;
  har_file: string;
  duration_seconds: number;
  metadata: Record<string, unknown>;
}

export interface RecorderStatus {
  state: RecorderState;
  is_recording: boolean;
  current_session: RecordingSession | null;
  total_entries: number;
}

export interface StartRecordingRequest {
  session_name?: string;
  metadata?: Record<string, unknown>;
  save_dir?: string | null;
}

export interface ReplayRequest {
  har_file: string;
  filter_url?: string | null;
  filter_method?: string | null;
  max_entries?: number | null;
  base_url?: string;
  ignore_headers?: string[];
  ignore_body_keys?: string[];
  strict_mode?: boolean;
}

export interface DiffItem {
  path: string;
  severity: "info" | "warning" | "error";
  recorded: unknown;
  actual: unknown;
  message: string;
}

export interface DiffReport {
  entry_index: number;
  url: string;
  method: string;
  matched: boolean;
  diffs: DiffItem[];
  diff_count: number;
  error_count: number;
  summary: string;
}

export interface PlaybackResult {
  entry_index: number;
  method: string;
  url: string;
  recorded_status: number;
  actual_status: number;
  recorded_elapsed_ms: number;
  actual_elapsed_ms: number;
  matched: boolean;
  diff_report: DiffReport | null;
  error: string;
}

export interface PlaybackReport {
  har_file: string;
  total_entries: number;
  matched_count: number;
  failed_count: number;
  error_count: number;
  pass_rate: number;
  results: PlaybackResult[];
  duration_seconds: number;
  summary: string;
}

export interface GenerateRequest {
  har_file: string;
  output_dir?: string;
  suite_name?: string;
  auto_assert?: boolean;
  assert_status?: boolean;
  max_assert_fields?: number;
  strict_assert?: boolean;
  priority?: string;
  tags?: string[];
}

export interface GenerateResult {
  output_file: string;
  case_count: number;
  skipped_entries: number;
  errors: string[];
}

// ── Smart Assertion ──────────────────────────────────────────

export interface FieldSchemaInfo {
  path: string;
  types: string[];
  dominant_type: string;
  required: boolean;
  occurrence_rate: number;
  null_rate: number;
  sample_count: number;
  sample_values: unknown[];
  value_pattern: string | null;
  min_value: number | null;
  max_value: number | null;
  min_length: number | null;
  max_length: number | null;
  distinct_count: number;
  warnings: string[];
}

export interface InferredSchemaInfo {
  case_id: string | null;
  case_name: string;
  fields: Record<string, FieldSchemaInfo>;
  sample_count: number;
  response_count: number;
  generated_at: string;
  top_level_type: string;
}

export interface AssertionItemInfo {
  path: string;
  expected: unknown;
  operator: string;
  message: string;
}

export interface SmartAssertionResponse {
  case_id: string | null;
  case_name: string;
  schema: InferredSchemaInfo | null;
  assertions: AssertionItemInfo[];
  sample_count: number;
}

export interface StructureChangeInfo {
  path: string;
  change_type: string;
  severity: string;
  expected: unknown;
  actual: unknown;
  message: string;
}

export interface ChangeDetectionResponse {
  case_id: string | null;
  case_name: string;
  changes: StructureChangeInfo[];
  has_warnings: boolean;
  has_errors: boolean;
  summary: string;
}

export interface SmartAssertionSuccessResponse<T> {
  success: boolean;
  data: T;
}
