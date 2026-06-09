import apiClient from "./client";

// client baseURL is "/api/v1", so we use relative paths
const BASE = "smart-assertions";

/**
 * 触发 Schema 推断
 */
export async function inferSchema(
  caseId: string,
  sampleLimit: number = 50,
  caseName?: string
) {
  const { data } = await apiClient.post(`${BASE}/${caseId}/infer`, {
    sample_limit: sampleLimit,
    case_name: caseName || "",
  });
  return data;
}

/**
 * 获取已推断的 Schema
 */
export async function getSchema(caseId: string) {
  const { data } = await apiClient.get(`${BASE}/${caseId}/schema`);
  return data;
}

/**
 * 获取智能生成的断言
 */
export async function getAssertions(
  caseId: string,
  excludePaths?: string[],
  includeOnly?: string[]
) {
  const params: string[][] = [];
  if (excludePaths?.length) {
    excludePaths.forEach((p) => params.push(["exclude_paths", p]));
  }
  if (includeOnly?.length) {
    includeOnly.forEach((p) => params.push(["include_only", p]));
  }
  const queryString = params
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join("&");
  const url = queryString
    ? `${BASE}/${caseId}/assertions?${queryString}`
    : `${BASE}/${caseId}/assertions`;
  const { data } = await apiClient.get(url);
  return data;
}

/**
 * 检测响应结构变更
 */
export async function detectChanges(
  caseId: string,
  responseBody?: Record<string, unknown>
) {
  const { data } = await apiClient.post(`${BASE}/${caseId}/detect`, {
    case_id: caseId,
    response_body: responseBody || undefined,
  });
  return data;
}

/**
 * 清除缓存的 Schema
 */
export async function clearSchema(caseId: string) {
  const { data } = await apiClient.delete(`${BASE}/${caseId}/schema`);
  return data;
}
