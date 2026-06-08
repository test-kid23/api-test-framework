import { Menu, Sparkles } from "lucide-react"

export function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-14 bg-[#0F172A] border-b border-slate-700/50 flex items-center px-6">
      <div className="flex items-center gap-3">
        <Sparkles className="h-5 w-5 text-blue-400" />
        <span className="text-white font-semibold text-lg tracking-tight">
          React + shadcn/ui
        </span>
        <span className="text-slate-400 text-sm ml-2">组件展示 Demo</span>
      </div>
      <div className="ml-auto flex items-center gap-3">
        <span className="px-3 py-1 text-xs font-medium rounded-full bg-blue-500/20 text-blue-300 border border-blue-500/30">
          React 18
        </span>
        <span className="px-3 py-1 text-xs font-medium rounded-full bg-zinc-500/20 text-zinc-300 border border-zinc-500/30">
          shadcn/ui
        </span>
        <span className="px-3 py-1 text-xs font-medium rounded-full bg-sky-500/20 text-sky-300 border border-sky-500/30">
          Tailwind CSS
        </span>
      </div>
    </nav>
  )
}
