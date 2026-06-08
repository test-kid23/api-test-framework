import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { Home, ChevronRight, Folder, FileText } from "lucide-react"

export function NavSection() {
  return (
    <section id="navigation" className="mb-10">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
          <h2 className="text-xl font-bold text-slate-900">导航 Navigation</h2>
          <p className="text-sm text-slate-500 mt-1">标签页、面包屑、分页组件</p>
        </div>
        <div className="p-6 space-y-8">
          {/* Tabs */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">标签页 Tabs</h3>
            <Tabs defaultValue="overview" className="w-full max-w-lg">
              <TabsList>
                <TabsTrigger value="overview">概览</TabsTrigger>
                <TabsTrigger value="cases">测试用例</TabsTrigger>
                <TabsTrigger value="reports">测试报告</TabsTrigger>
                <TabsTrigger value="settings">设置</TabsTrigger>
              </TabsList>
              <TabsContent value="overview" className="p-4 border rounded-md mt-2">
                <p className="text-sm text-slate-600">
                  今日执行 128 条用例，通过率 97.6%，平均响应时间 234ms。
                </p>
              </TabsContent>
              <TabsContent value="cases" className="p-4 border rounded-md mt-2">
                <p className="text-sm text-slate-600">
                  共 342 条测试用例，覆盖 45 个 API 接口。可在此管理用例增删改查。
                </p>
              </TabsContent>
              <TabsContent value="reports" className="p-4 border rounded-md mt-2">
                <p className="text-sm text-slate-600">
                  最近 7 天生成了 24 份测试报告，支持 HTML / Allure / JSON 格式导出。
                </p>
              </TabsContent>
              <TabsContent value="settings" className="p-4 border rounded-md mt-2">
                <p className="text-sm text-slate-600">
                  配置全局超时、重试策略、并发数等执行参数。当前环境：Staging。
                </p>
              </TabsContent>
            </Tabs>
          </div>

          <Separator />

          {/* Breadcrumb */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">面包屑 Breadcrumb</h3>
            <nav className="flex items-center gap-1 text-sm text-slate-500">
              <button className="flex items-center gap-1 hover:text-slate-900 transition-colors cursor-pointer">
                <Home className="h-3.5 w-3.5" />
                <span>首页</span>
              </button>
              <ChevronRight className="h-4 w-4 text-slate-300" />
              <button className="flex items-center gap-1 hover:text-slate-900 transition-colors cursor-pointer">
                <Folder className="h-3.5 w-3.5" />
                <span>项目中心</span>
              </button>
              <ChevronRight className="h-4 w-4 text-slate-300" />
              <button className="flex items-center gap-1 hover:text-slate-900 transition-colors cursor-pointer">
                <FileText className="h-3.5 w-3.5" />
                <span>API 测试框架</span>
              </button>
              <ChevronRight className="h-4 w-4 text-slate-300" />
              <span className="text-slate-900 font-medium">用例详情</span>
            </nav>
          </div>

          <Separator />

          {/* Pagination */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">分页 Pagination</h3>
            <div className="flex items-center justify-between max-w-lg border rounded-lg px-4 py-2.5 bg-white">
              <span className="text-sm text-slate-500">共 342 条</span>
              <div className="flex items-center gap-1">
                <button className="px-3 py-1.5 text-sm rounded-md border hover:bg-slate-50 disabled:opacity-40 cursor-pointer" disabled>
                  上一页
                </button>
                <button className="px-3 py-1.5 text-sm rounded-md bg-primary text-primary-foreground cursor-pointer">
                  1
                </button>
                <button className="px-3 py-1.5 text-sm rounded-md hover:bg-slate-50 cursor-pointer">
                  2
                </button>
                <button className="px-3 py-1.5 text-sm rounded-md hover:bg-slate-50 cursor-pointer">
                  3
                </button>
                <span className="px-1 text-slate-400">...</span>
                <button className="px-3 py-1.5 text-sm rounded-md hover:bg-slate-50 cursor-pointer">
                  18
                </button>
                <button className="px-3 py-1.5 text-sm rounded-md border hover:bg-slate-50 cursor-pointer">
                  下一页
                </button>
              </div>
              <div className="flex items-center gap-1 text-sm text-slate-500">
                <span>跳至</span>
                <input className="w-12 h-8 text-center border rounded-md text-sm" defaultValue="1" />
                <span>页</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
