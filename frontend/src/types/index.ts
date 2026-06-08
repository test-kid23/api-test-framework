export interface TestCase {
  id: string;
  name: string;
  yaml_content: string;
  tags: string[];
  priority: "P0" | "P1" | "P2" | "P3";
  description?: string;
  created_at: string;
  updated_at: string;
  version: number;
}

export interface TestCaseCreate {
  name: string;
  yaml_content: string;
  tags: string[];
  priority: "P0" | "P1" | "P2" | "P3";
  description?: string;
}

export interface TestCaseUpdate {
  name?: string;
  yaml_content?: string;
  tags?: string[];
  priority?: "P0" | "P1" | "P2" | "P3";
  description?: string;
}

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

export interface Execution {
  id: string;
  suite_name: string;
  status: "pending" | "running" | "passed" | "failed" | "cancelled";
  trigger: "manual" | "scheduled" | "ci";
  env_name: string;
  started_at: string | null;
  finished_at: string | null;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  celery_task_id?: string;
  created_at: string;
}

export interface ExecutionDetail extends Execution {
  case_results: CaseResult[];
}

export interface CaseResult {
  case_id: string;
  case_name: string;
  status: "passed" | "failed" | "error" | "skipped";
  elapsed_ms: number;
  error_message?: string;
  request_summary?: string;
}

export interface DashboardData {
  pass_rate_trend: { date: string; rate: number }[];
  failure_categories: { category: string; count: number }[];
  top_unstable: { case_name: string; failure_count: number }[];
}

export interface Environment {
  id: string;
  name: string;
  description: string;
  base_url: string;
  ws_url?: string;
  variable_count: number;
  created_at: string;
  updated_at: string;
}

export interface EnvironmentCreate {
  name: string;
  description: string;
  base_url: string;
  ws_url?: string;
  variables?: Record<string, string>;
}

export interface EnvironmentUpdate {
  name?: string;
  description?: string;
  base_url?: string;
  ws_url?: string;
  variables?: Record<string, string>;
}
