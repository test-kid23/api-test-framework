import { useState } from "react"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Checkbox } from "@/components/ui/checkbox"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

export function FormSection() {
  const [checkboxValues, setCheckboxValues] = useState<string[]>(["react"])
  const [radioValue, setRadioValue] = useState("vue")
  const [switchOn, setSwitchOn] = useState(true)

  return (
    <section id="forms" className="mb-10">
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white">
          <h2 className="text-xl font-bold text-slate-900">表单 Form</h2>
          <p className="text-sm text-slate-500 mt-1">常用表单控件一览，均可交互</p>
        </div>
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Input */}
            <div className="space-y-2">
              <Label htmlFor="name">姓名</Label>
              <Input id="name" placeholder="请输入姓名" defaultValue="张三" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="email">邮箱</Label>
              <Input id="email" type="email" placeholder="name@example.com" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input id="password" type="password" placeholder="请输入密码" value="password123" readOnly />
            </div>

            {/* Select */}
            <div className="space-y-2">
              <Label>城市</Label>
              <Select defaultValue="beijing">
                <SelectTrigger>
                  <SelectValue placeholder="请选择城市" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="beijing">北京</SelectItem>
                  <SelectItem value="shanghai">上海</SelectItem>
                  <SelectItem value="shenzhen">深圳</SelectItem>
                  <SelectItem value="hangzhou">杭州</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Checkbox Group */}
            <div className="space-y-3">
              <Label>技术偏好（多选）</Label>
              <div className="flex flex-col gap-2">
                {[
                  { value: "react", label: "React" },
                  { value: "vue", label: "Vue" },
                  { value: "angular", label: "Angular / Svelte" },
                ].map(({ value, label }) => (
                  <div key={value} className="flex items-center space-x-2">
                    <Checkbox
                      id={`cb-${value}`}
                      checked={checkboxValues.includes(value)}
                      onCheckedChange={(checked) => {
                        if (checked) {
                          setCheckboxValues([...checkboxValues, value])
                        } else {
                          setCheckboxValues(checkboxValues.filter((v) => v !== value))
                        }
                      }}
                    />
                    <label htmlFor={`cb-${value}`} className="text-sm cursor-pointer">
                      {label}
                    </label>
                  </div>
                ))}
              </div>
            </div>

            {/* Radio Group */}
            <div className="space-y-3">
              <Label>主要使用框架</Label>
              <RadioGroup value={radioValue} onValueChange={setRadioValue}>
                {[
                  { value: "react", label: "React" },
                  { value: "vue", label: "Vue" },
                  { value: "other", label: "其他" },
                ].map(({ value, label }) => (
                  <div key={value} className="flex items-center space-x-2">
                    <RadioGroupItem value={value} id={`rb-${value}`} />
                    <label htmlFor={`rb-${value}`} className="text-sm cursor-pointer">
                      {label}
                    </label>
                  </div>
                ))}
              </RadioGroup>
            </div>

            {/* Switch */}
            <div className="space-y-3">
              <Label>通知设置</Label>
              <div className="flex flex-col gap-3">
                <div className="flex items-center space-x-2">
                  <Switch id="email-notif" checked={switchOn} onCheckedChange={setSwitchOn} />
                  <Label htmlFor="email-notif" className="cursor-pointer">邮件通知 {switchOn ? "（已开启）" : "（已关闭）"}</Label>
                </div>
                <div className="flex items-center space-x-2">
                  <Switch id="sms-notif" />
                  <Label htmlFor="sms-notif" className="cursor-pointer">短信通知</Label>
                </div>
              </div>
            </div>

            {/* DatePicker */}
            <div className="space-y-2">
              <Label htmlFor="date">日期选择</Label>
              <Input id="date" type="date" defaultValue="2026-06-08" />
            </div>
          </div>

          {/* Textarea */}
          <div className="mt-6 space-y-2">
            <Label htmlFor="desc">项目描述</Label>
            <Textarea
              id="desc"
              placeholder="请输入项目描述..."
              defaultValue="这是一个基于 React + shadcn/ui 的现代化前端项目，采用 Tailwind CSS 进行样式管理，组件设计遵循无障碍标准。"
              rows={3}
            />
          </div>
        </div>
      </div>
    </section>
  )
}
