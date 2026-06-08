import { Navbar } from "./components/Navbar"
import { Sidebar } from "./components/Sidebar"
import { Footer } from "./components/Footer"
import { ButtonSection } from "./components/sections/ButtonSection"
import { FormSection } from "./components/sections/FormSection"
import { DataSection } from "./components/sections/DataSection"
import { NavSection } from "./components/sections/NavSection"
import { FeedbackSection } from "./components/sections/FeedbackSection"

function App() {
  return (
    <div className="min-h-screen bg-[#F1F5F9]">
      <Navbar />
      <Sidebar />

      <main className="ml-48 pt-14">
        <div className="max-w-5xl mx-auto px-8 py-8">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-slate-900">React + shadcn/ui 组件展示</h1>
            <p className="text-slate-500 mt-2">
              基于 Radix UI 原语的现代 React 组件库，源码级集成 · 高度可定制 · 无障碍优先
            </p>
          </div>

          <ButtonSection />
          <FormSection />
          <DataSection />
          <NavSection />
          <FeedbackSection />
        </div>

        <Footer />
      </main>
    </div>
  )
}

export default App
