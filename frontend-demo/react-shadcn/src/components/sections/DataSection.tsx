import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { ExternalLink } from "lucide-react"

const tableData = [
  { id: 1, name: "用户登录接口", method: "POST", status: "通过", duration: "235ms" },
  { id: 2, name: "订单列表查询", method: "GET", status: "通过", duration: "412ms" },
  { id: 3, name: "商品详情获取", method: "GET", status: "失败", duration: "89ms" },
  { id: 4, name: "数据导出任务", method: "POST", status: "运行中", duration: "1.2s" },
]

export function DataSection() {
  return (
    <section id="data" className="mb-10">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
          <h2 className="text-xl font-bold text-slate-900">数据展示 Data Display</h2>
          <p className="text-sm text-slate-500 mt-1">表格、卡片、标签组件一览</p>
        </div>
        <div className="p-6 space-y-8">
          {/* Table */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">数据表格</h3>
            <div className="border rounded-lg overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">ID</TableHead>
                    <TableHead>接口名称</TableHead>
                    <TableHead>方法</TableHead>
                    <TableHead>状态</TableHead>
                    <TableHead className="text-right">耗时</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tableData.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell className="font-mono text-xs">{row.id}</TableCell>
                      <TableCell className="font-medium">{row.name}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className="font-mono text-xs">
                          {row.method}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            row.status === "通过" ? "default" : row.status === "失败" ? "destructive" : "secondary"
                          }
                        >
                          {row.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right text-slate-500">{row.duration}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </div>

          <Separator />

          {/* Card */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">卡片组件</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">API 测试框架</CardTitle>
                  <CardDescription>企业级自动化测试解决方案</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-slate-600">
                    支持 HTTP、gRPC、WebSocket 多协议测试，内置断言引擎与报告生成，
                    具备分布式执行能力。
                  </p>
                </CardContent>
                <CardFooter>
                  <Button variant="outline" size="sm">
                    <ExternalLink className="mr-2 h-3 w-3" />
                    查看详情
                  </Button>
                </CardFooter>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">多协议支持</CardTitle>
                  <CardDescription>覆盖主流 API 协议</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    <Badge>HTTP/HTTPS</Badge>
                    <Badge variant="secondary">gRPC</Badge>
                    <Badge variant="outline">WebSocket</Badge>
                    <Badge variant="secondary">GraphQL</Badge>
                    <Badge variant="outline">TCP</Badge>
                  </div>
                </CardContent>
                <CardFooter>
                  <p className="text-xs text-slate-400">已集成 5 种协议支持</p>
                </CardFooter>
              </Card>
            </div>
          </div>

          <Separator />

          {/* Tags */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">标签 / Badge</h3>
            <div className="flex flex-wrap gap-2">
              <Badge>Default</Badge>
              <Badge variant="secondary">Secondary</Badge>
              <Badge variant="destructive">Destructive</Badge>
              <Badge variant="outline">Outline</Badge>
              <Badge className="bg-emerald-500 hover:bg-emerald-500/80">Success</Badge>
              <Badge className="bg-amber-500 hover:bg-amber-500/80">Warning</Badge>
              <Badge className="bg-purple-500 hover:bg-purple-500/80">Info</Badge>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
