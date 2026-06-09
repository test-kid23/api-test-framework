import { useMemo } from "react";
import { useDashboard } from "@/hooks/useReports";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, AreaChart,
} from "recharts";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

// CSS variable-based chart colors (no hardcoded hex)
const CHART_COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--destructive))",
  "hsl(32 95% 44%)",
  "hsl(262 83% 58%)",
  "hsl(175 84% 32%)",
  "hsl(340 82% 52%)",
];

export function DashboardPage() {
  const days = 30;
  const { data, isLoading } = useDashboard(days);

  // Compute KPI stats
  const kpis = useMemo(() => {
    if (!data?.pass_rate_trend?.length) return null;
    const trend = data.pass_rate_trend;
    const latest = trend[trend.length - 1];
    const mid = trend[Math.floor(trend.length / 2)];
    const deltaRate = mid?.rate ? latest.rate - mid.rate : 0;
    const avgRate = trend.reduce((s, t) => s + t.rate, 0) / trend.length;

    return {
      currentRate: latest.rate,
      avgRate,
      deltaRate,
    };
  }, [data]);

  const passRateTrend = data?.pass_rate_trend || [];
  const topFailures = data?.top_unstable || [];

  // Failure categories for breakdown visualization
  const failureTotal = topFailures.reduce((s, f) => s + (f.failure_count || 0), 0);
  const failureCategories = topFailures.map((f) => ({
    name: f.case_name,
    count: f.failure_count || 0,
  }));

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-28 w-full" />
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-[380px]" />
          <Skeleton className="h-[380px]" />
        </div>
      </div>
    );
  }

  // No data state
  if (!passRateTrend.length && !topFailures.length) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">报告看板</h1>
        </div>
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <p className="text-lg mb-1">暂无报告数据</p>
            <p className="text-sm">执行测试后将自动生成报告</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">报告看板</h1>
      </div>

      {/* KPI Cards */}
      {kpis && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <Card>
            <CardContent className="pt-5">
              <p className="text-sm text-muted-foreground">当前通过率</p>
              <p className="text-2xl font-bold mt-1 text-emerald-600">
                {kpis.currentRate.toFixed(1)}%
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                最近 {days} 天
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-5">
              <p className="text-sm text-muted-foreground">平均通过率</p>
              <p className="text-2xl font-bold mt-1">{kpis.avgRate.toFixed(1)}%</p>
              <p className="text-xs text-muted-foreground mt-1">
                {passRateTrend.length} 个数据点
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-5">
              <p className="text-sm text-muted-foreground">趋势变化</p>
              <div className="flex items-center gap-1 mt-1">
                {kpis.deltaRate > 0 ? (
                  <TrendingUp className="h-5 w-5 text-emerald-500" />
                ) : kpis.deltaRate < 0 ? (
                  <TrendingDown className="h-5 w-5 text-destructive" />
                ) : (
                  <Minus className="h-5 w-5 text-muted-foreground" />
                )}
                <span className={`text-2xl font-bold ${
                  kpis.deltaRate > 0 ? "text-emerald-600" : kpis.deltaRate < 0 ? "text-destructive" : ""
                }`}>
                  {kpis.deltaRate > 0 ? "+" : ""}{kpis.deltaRate.toFixed(1)}%
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">较前半段</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-5">
              <p className="text-sm text-muted-foreground">不稳定用例</p>
              <p className="text-2xl font-bold mt-1 text-destructive">
                {topFailures.length}
              </p>
              <p className="text-xs text-muted-foreground mt-1">个高频失败</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-5">
              <p className="text-sm text-muted-foreground">失败总数</p>
              <p className="text-2xl font-bold mt-1">{failureTotal}</p>
              <p className="text-xs text-muted-foreground mt-1">次</p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Pass Rate Trend - 3/5 width */}
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle className="text-base">通过率趋势</CardTitle>
          </CardHeader>
          <CardContent>
            {passRateTrend.length > 0 ? (
              <ResponsiveContainer width="100%" height={320}>
                <AreaChart data={passRateTrend}>
                  <defs>
                    <linearGradient id="passRateGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.2} />
                      <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted/50" />
                  <XAxis
                    dataKey="date"
                    className="text-xs"
                    tick={{ fontSize: 12 }}
                    tickFormatter={(v) => v?.slice(5) || v}
                  />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} unit="%" />
                  <Tooltip
                    formatter={(value: number) => [`${value.toFixed(1)}%`, "通过率"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="rate"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    fill="url(#passRateGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[320px] flex items-center justify-center text-muted-foreground">
                暂无趋势数据
              </div>
            )}
          </CardContent>
        </Card>

        {/* Top Failures - 2/5 width */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">失败最多的用例</CardTitle>
          </CardHeader>
          <CardContent>
            {failureCategories.length > 0 ? (
              <div className="space-y-4">
                {failureCategories.map((item, idx) => {
                  const pct = failureTotal > 0 ? (item.count / failureTotal) * 100 : 0;
                  return (
                    <div key={item.name} className="space-y-1.5">
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2 min-w-0">
                          <Badge
                            variant="outline"
                            className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center p-0 text-xs"
                          >
                            {idx + 1}
                          </Badge>
                          <span className="truncate font-medium">{item.name}</span>
                        </div>
                        <span className="shrink-0 text-xs text-muted-foreground ml-2">
                          {item.count} 次
                        </span>
                      </div>
                      <Progress
                        value={pct}
                        className="h-2"
                        style={
                          {
                            "--progress-background": CHART_COLORS[idx % CHART_COLORS.length],
                          } as React.CSSProperties
                        }
                      />
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="h-[320px] flex items-center justify-center text-muted-foreground">
                暂无失败数据
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
