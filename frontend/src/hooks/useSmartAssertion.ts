import { useState, useCallback } from "react";
import * as assertionsApi from "@/api/assertions";
import type {
  InferredSchemaInfo,
  AssertionItemInfo,
  StructureChangeInfo,
} from "@/types";

interface UseSmartAssertionReturn {
  /** 推断的 Schema */
  schema: InferredSchemaInfo | null;
  /** 生成的断言列表 */
  assertions: AssertionItemInfo[];
  /** 变更检测结果 */
  changes: StructureChangeInfo[];
  /** 变更摘要 */
  changeSummary: string;
  /** 是否正在加载 */
  loading: boolean;
  /** 错误信息 */
  error: string | null;
  /** 触发 Schema 推断 */
  inferSchema: (caseId: string, sampleLimit?: number, caseName?: string) => Promise<void>;
  /** 获取已推断的 Schema */
  fetchSchema: (caseId: string) => Promise<void>;
  /** 获取生成的断言 */
  fetchAssertions: (caseId: string, excludePaths?: string[], includeOnly?: string[]) => Promise<void>;
  /** 检测响应结构变更 */
  detectChanges: (caseId: string, responseBody?: Record<string, unknown>) => Promise<void>;
  /** 清除缓存的 Schema */
  clearSchema: (caseId: string) => Promise<void>;
  /** 重置状态 */
  reset: () => void;
}

export function useSmartAssertion(): UseSmartAssertionReturn {
  const [schema, setSchema] = useState<InferredSchemaInfo | null>(null);
  const [assertions, setAssertions] = useState<AssertionItemInfo[]>([]);
  const [changes, setChanges] = useState<StructureChangeInfo[]>([]);
  const [changeSummary, setChangeSummary] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wrap = useCallback(
    async <T>(fn: () => Promise<T>): Promise<T | undefined> => {
      setLoading(true);
      setError(null);
      try {
        return await fn();
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : "未知错误";
        setError(msg);
        return undefined;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const inferSchema = useCallback(
    async (caseId: string, sampleLimit = 50, caseName?: string) => {
      const result = await wrap(() =>
        assertionsApi.inferSchema(caseId, sampleLimit, caseName)
      );
      if (result) {
        setSchema(result);
        setAssertions([]);
        setChanges([]);
        setChangeSummary("");
      }
    },
    [wrap]
  );

  const fetchSchema = useCallback(
    async (caseId: string) => {
      const result = await wrap(() => assertionsApi.getSchema(caseId));
      if (result) {
        setSchema(result);
      }
    },
    [wrap]
  );

  const fetchAssertions = useCallback(
    async (caseId: string, excludePaths?: string[], includeOnly?: string[]) => {
      const result = await wrap(() =>
        assertionsApi.getAssertions(caseId, excludePaths, includeOnly)
      );
      if (result) {
        if (result.schema) setSchema(result.schema);
        setAssertions(result.assertions || []);
      }
    },
    [wrap]
  );

  const detectChanges = useCallback(
    async (caseId: string, responseBody?: Record<string, unknown>) => {
      const result = await wrap(() =>
        assertionsApi.detectChanges(caseId, responseBody)
      );
      if (result) {
        setChanges(result.changes || []);
        setChangeSummary(result.summary || "");
      }
    },
    [wrap]
  );

  const clearSchema = useCallback(
    async (caseId: string) => {
      await wrap(() => assertionsApi.clearSchema(caseId));
      setSchema(null);
      setAssertions([]);
      setChanges([]);
      setChangeSummary("");
    },
    [wrap]
  );

  const reset = useCallback(() => {
    setSchema(null);
    setAssertions([]);
    setChanges([]);
    setChangeSummary("");
    setError(null);
  }, []);

  return {
    schema,
    assertions,
    changes,
    changeSummary,
    loading,
    error,
    inferSchema,
    fetchSchema,
    fetchAssertions,
    detectChanges,
    clearSchema,
    reset,
  };
}
