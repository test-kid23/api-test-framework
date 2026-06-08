import { useState, useEffect } from "react"
import { cn } from "@/lib/utils"

const sections = [
  { id: "buttons", label: "按钮 Button", icon: "▢" },
  { id: "forms", label: "表单 Form", icon: "☰" },
  { id: "data", label: "数据展示 Data", icon: "⊞" },
  { id: "navigation", label: "导航 Navigation", icon: "☰" },
  { id: "feedback", label: "反馈 Feedback", icon: "◉" },
]

export function Sidebar() {
  const [active, setActive] = useState("buttons")

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActive(entry.target.id)
          }
        })
      },
      { rootMargin: "-20% 0px -70% 0px" }
    )

    sections.forEach(({ id }) => {
      const el = document.getElementById(id)
      if (el) observer.observe(el)
    })

    return () => observer.disconnect()
  }, [])

  const scrollTo = (id: string) => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" })
    }
  }

  return (
    <aside className="fixed top-14 left-0 bottom-0 w-48 bg-[#F8FAFC] border-r border-slate-200 z-40 overflow-y-auto">
      <div className="p-4">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
          组件导航
        </p>
        <nav className="space-y-1">
          {sections.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => scrollTo(id)}
              className={cn(
                "w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer",
                active === id
                  ? "bg-blue-50 text-blue-700 border-l-2 border-blue-600"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 border-l-2 border-transparent"
              )}
            >
              {label}
            </button>
          ))}
        </nav>
      </div>
    </aside>
  )
}
