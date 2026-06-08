import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { Loader2, Mail, Heart, Settings } from "lucide-react"

export function ButtonSection() {
  return (
    <section id="buttons" className="mb-10">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
          <h2 className="text-xl font-bold text-slate-900">按钮 Button</h2>
          <p className="text-sm text-slate-500 mt-1">五种变体 × 三种尺寸，支持图标、加载和禁用状态</p>
        </div>
        <div className="p-6 space-y-6">
          {/* Variant Matrix */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">变体 × 尺寸矩阵</h3>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className="text-left text-xs text-slate-400 font-medium p-2 w-20"></th>
                    <th className="text-center text-xs text-slate-400 font-medium p-2">Small</th>
                    <th className="text-center text-xs text-slate-400 font-medium p-2">Default</th>
                    <th className="text-center text-xs text-slate-400 font-medium p-2">Large</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {([
                    { label: "Primary", variant: "default" as const },
                    { label: "Secondary", variant: "secondary" as const },
                    { label: "Outline", variant: "outline" as const },
                    { label: "Ghost", variant: "ghost" as const },
                    { label: "Destructive", variant: "destructive" as const },
                  ]).map(({ label, variant }) => (
                    <tr key={label}>
                      <td className="p-2 text-xs font-medium text-slate-500">{label}</td>
                      <td className="p-2 text-center">
                        <Button variant={variant} size="sm">按钮</Button>
                      </td>
                      <td className="p-2 text-center">
                        <Button variant={variant}>按钮</Button>
                      </td>
                      <td className="p-2 text-center">
                        <Button variant={variant} size="lg">按钮</Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <Separator />

          {/* Icon Buttons */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">带图标按钮</h3>
            <div className="flex flex-wrap gap-3">
              <Button><Mail className="mr-2 h-4 w-4" /> 邮箱</Button>
              <Button variant="secondary"><Settings className="mr-2 h-4 w-4" /> 设置</Button>
              <Button variant="outline"><Heart className="mr-2 h-4 w-4" /> 收藏</Button>
              <Button variant="ghost"><Heart className="mr-2 h-4 w-4" /> 喜欢</Button>
            </div>
          </div>

          <Separator />

          {/* States */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">状态展示</h3>
            <div className="flex flex-wrap gap-3">
              <Button disabled><Loader2 className="mr-2 h-4 w-4 animate-spin" /> 加载中</Button>
              <Button disabled>已禁用</Button>
              <Button variant="outline" disabled>禁用边框</Button>
              <Button variant="secondary" disabled>禁用次要</Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
