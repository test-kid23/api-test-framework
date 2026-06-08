import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { toast } from "sonner"
import { MessageSquare, CheckCircle, AlertTriangle } from "lucide-react"

export function FeedbackSection() {
  const [dialogOpen, setDialogOpen] = useState(false)

  return (
    <section id="feedback" className="mb-10">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
          <h2 className="text-xl font-bold text-slate-900">反馈 Feedback</h2>
          <p className="text-sm text-slate-500 mt-1">对话框、消息提示、骨架屏组件</p>
        </div>
        <div className="p-6 space-y-8">
          {/* Dialog */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">对话框 Dialog</h3>
            <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
              <DialogTrigger asChild>
                <Button>
                  <MessageSquare className="mr-2 h-4 w-4" />
                  打开对话框
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>确认删除测试用例？</DialogTitle>
                  <DialogDescription>
                    该操作将永久删除"用户登录接口验证"测试用例及其关联的所有执行历史记录，此操作不可恢复。
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter className="sm:justify-end gap-2">
                  <Button variant="outline" onClick={() => setDialogOpen(false)}>
                    取消
                  </Button>
                  <Button variant="destructive" onClick={() => {
                    setDialogOpen(false)
                    toast.success("测试用例已成功删除")
                  }}>
                    确认删除
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          <Separator />

          {/* Toast Messages */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">消息提示 Toast</h3>
            <div className="flex flex-wrap gap-3">
              <Button
                variant="default"
                onClick={() => toast.success("操作成功！测试用例已保存。")}
              >
                <CheckCircle className="mr-2 h-4 w-4" />
                成功消息
              </Button>
              <Button
                variant="secondary"
                onClick={() => toast.info("定时任务将在 5 分钟后开始执行。")}
              >
                普通消息
              </Button>
              <Button
                variant="destructive"
                onClick={() => toast.error("接口调用失败：连接超时，请重试。")}
              >
                <AlertTriangle className="mr-2 h-4 w-4" />
                错误消息
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  toast("新版本 v2.3.0 已发布", {
                    description: "新增 WebSocket 协议支持，优化了报告生成速度。",
                    action: { label: "查看", onClick: () => console.log("查看") },
                  })
                }
              >
                带操作消息
              </Button>
            </div>
          </div>

          <Separator />

          {/* Skeleton */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">骨架屏 Skeleton</h3>
            <div className="border rounded-lg p-6 space-y-4 max-w-md">
              <div className="flex items-center space-x-4">
                <Skeleton className="h-12 w-12 rounded-full" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-[200px]" />
                  <Skeleton className="h-4 w-[150px]" />
                </div>
              </div>
              <Skeleton className="h-32 w-full rounded-lg" />
              <div className="space-y-2">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-[80%]" />
                <Skeleton className="h-4 w-[60%]" />
              </div>
              <div className="flex gap-2">
                <Skeleton className="h-10 w-24 rounded-md" />
                <Skeleton className="h-10 w-24 rounded-md" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
