import { useState } from "react";
import { useDashboard } from "@/hooks/useReports";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { Badge } from "@/components/ui/badge";

const COLORS = ["#ef4444", "#f97316", "#eab308", "#3b82f6", "#8b5cf6", "#22c55e"];

export function DashboardPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, isError } = useDashboard(days);

  // Mock data for when backend is not ready
  const mockTrend = Array.from({ length: 30 }, (_, i) => ({
    date: `06-${String(i + 1).padStart(2, "0")}`,
    rate: 85 + Math.random() * 15,
  }));

  const mockCategories = [
    { category: "状态码错误", count: 23 },
    { category: "响应超时", count: 15 },
    { category: "JSON 解析失败", count: 8 },
    { category: "数据断言失败", count: 12 },
    { category: "认证失败", count: 5 },
  ];

  const mockUnstable = [
    { case_name: "用户登录接口", failure_count: 8 },
    { case_name: "订单创建接口", failure_count: 6 },
    { case_name: "支付回调接口", failure_count: 5 },
    { case_name: "商品列表接口", failure_count: 4 },
    { case_name: "库存查询接口", failure_count: 3 },
  ];

  const passRateTrend = data?.pass_rate_trend?.length
    ? data.pass_rate_trend.map((d) => ({ date: d.date, rate: d.rate }))
    : mockTrend;

  const failureCategories = data?.failure_categories?.length
    ? data.failure_categories
    : mockCategories;

  const topUnstable = data?.top_unstable?.length ? data.top_unstable : mockUnstable;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-[400px]" />
          <Skeleton className="h-[400px]" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">报告看板</h1>
        <Select value={String(days)} onValueChange={(v) => setDays(Number(v))}>
          <SelectTrigger className="w-[140px]">
            <SelectValue placeholder="时间范围" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7">最近 7 天</SelectItem>
            <SelectItem value="14">最近 14 天</SelectItem>
            <SelectItem value="30">最近 30 天</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isError && (
        <Card className="border-yellow-200 bg-yellow-50 dark:bg-yellow-950">
          <CardContent className="pt-6 text-sm text-yellow-800 dark:text-yellow-200">
            后端报告 API 暂未就绪，当前展示模拟数据。联调后自动切换真实数据。
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pass Rate Trend */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">通过率趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={passRateTrend}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="date"
                  className="text-xs"
                  tick={{ fontSize: 12 }}
                />
                <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(value: number) => [`${value.toFixed(1)}%`, "通过率"]}
                />
                <Line
                  type="monotone"
                  dataKey="rate"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Failure Categories Pie Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">失败原因分类</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={failureCategories}
                  dataKey="count"
                  nameKey="category"
                  cx="50%"
                  cy="50%"
                  outerRadius={100}
                  label={({ category, count }) =>
                    `${category}: ${count}`
                  }
                >
                  {failureCategories.map((_, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[index % COLORS.length]}
                    />
                  ))}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Top 5 Unstable APIs */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Top 5 不稳定接口</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {topUnstable.map((item, index) => (
              <div
                key={item.case_name}
                className="flex items-center justify-between rounded-lg border p-3"
              >
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="w-7 h-7 rounded-full flex items-center justify-center p-0">
                    {index + 1}
                  </Badge>
                  <span className="font-medium">{item.case_name}</span>
                </div>
                <Badge variant="destructive">{item.failure_count} 次失败</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
