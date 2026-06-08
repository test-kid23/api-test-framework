---
name: tdesign-vs-shadcn-comparison
overview: 创建一个独立的 React 前端 Demo 项目，在同一页面上并排对比展示 TDesign React 和 shadcn/ui 两套组件库的风格特点，帮助用户做技术选型。
design:
  architecture:
    framework: react
    component: shadcn
  styleKeywords:
    - 专业对比展示
    - 深色导航
    - 白色卡片
    - 左右分栏
    - 企业级
  fontSystem:
    fontFamily: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
    heading:
      size: 28px
      weight: 700
    subheading:
      size: 20px
      weight: 600
    body:
      size: 14px
      weight: 400
  colorSystem:
    primary:
      - "#0052D9"
      - "#1E293B"
      - "#18181B"
    background:
      - "#F1F5F9"
      - "#FFFFFF"
      - "#F8FAFC"
    text:
      - "#0F172A"
      - "#64748B"
      - "#FFFFFF"
    functional:
      - "#22C55E"
      - "#F59E0B"
      - "#EF4444"
      - "#E2E8F0"
todos:
  - id: scaffold-vite-project
    content: 使用 [skill:prototype] 在 frontend-demo/ 下创建 Vite + React 18 + TypeScript 5 项目骨架，安装 Tailwind CSS 3 并配置
    status: pending
  - id: install-tdesign
    content: 安装 TDesign React 和 tdesign-icons-react，在入口文件导入全局 CSS
    status: pending
    dependencies:
      - scaffold-vite-project
  - id: setup-shadcn
    content: 手动创建 src/lib/utils.ts 的 cn 工具函数，配置 index.css 中的 shadcn CSS 变量主题，手动复制 9 个所需 shadcn/ui 组件源码到 src/components/ui/
    status: pending
    dependencies:
      - scaffold-vite-project
  - id: build-compare-layout
    content: 构建顶部导航、左侧锚点导航和页面整体左右分栏框架
    status: pending
    dependencies:
      - scaffold-vite-project
  - id: implement-button-compare
    content: 实现按钮对比区：四种变体 × 三种尺寸矩阵 + Loading/Disabled 状态
    status: pending
    dependencies:
      - install-tdesign
      - setup-shadcn
      - build-compare-layout
  - id: implement-form-compare
    content: 实现表单对比区：Input、Select、Checkbox、Radio、Switch、Textarea
    status: pending
    dependencies:
      - install-tdesign
      - setup-shadcn
      - build-compare-layout
  - id: implement-data-nav-feedback
    content: 实现数据展示（Table/Card/Tag）、导航（Tabs/Breadcrumb）、反馈（Dialog/Toast/Skeleton）三大对比区
    status: pending
    dependencies:
      - install-tdesign
      - setup-shadcn
      - build-compare-layout
---

## 产品概述

一个独立的组件库对比 Demo 页面，在同一个页面中左右并排展示 TDesign 和 shadcn/ui 两套组件库在相同场景下的实际渲染效果，帮助开发者在正式启动前端开发前做出组件库选择决策。

## 核心功能

- **并排对比布局**：页面整体左右分栏，左侧 TDesign，右侧 shadcn/ui，每个组件类型一个对比区域，一目了然
- **按钮组件对比**：展示 Primary/Secondary/Outline/Text 四种变体、S/M/L 三种尺寸、Loading 与 Disabled 状态
- **表单组件对比**：包含 Input、Select、Checkbox 组、Radio 组、Switch、Textarea 常用表单控件，均可交互
- **数据展示对比**：展示 Table、Card、Tag 组件
- **导航组件对比**：展示可切换的 Tabs、多级 Breadcrumb
- **反馈组件对比**：展示可触发的 Dialog 弹窗、Toast 消息、Skeleton 骨架屏
- **锚点导航**：左侧固定分类导航，点击可平滑滚动到对应对比区

## 技术方案

### 技术栈

- **构建工具**: Vite 5（快速 HMR、TypeScript 原生支持）
- **UI 框架**: React 18 + TypeScript 5
- **CSS 方案**: Tailwind CSS 3（为 shadcn/ui 提供原子化样式）+ TDesign 自带 CSS
- **组件库 A**: TDesign React（npm 包 `tdesign-react` + `tdesign-icons-react`）
- **组件库 B**: shadcn/ui（基于 Radix UI 原语，手动复制组件源码到 `src/components/ui/`）

### 实现策略

**同项目共存方案**：TDesign 组件带有 `t-` 前缀的专有 CSS 类名，shadcn/ui 使用 Tailwind 原子类，两套库各自独立的样式作用域，不存在冲突风险。在入口 `main.tsx` 中导入 TDesign 全局 CSS，同时引入 Tailwind 三层指令（`@tailwind base/components/utilities`）。

**对比页布局策略**：采用 flex 左右分栏 + 分区卡片式布局。顶部固定深色导航栏（56px），左侧 sticky 分类锚点导航（180px），主区域（剩余宽度）每个对比区一张白色卡片，卡片内部左半 TDesign 右半 shadcn，中间以竖线分隔。

**shadcn/ui 集成方式**：手动创建 `src/components/ui/` 目录，参考 shadcn/ui 官方源码手动复制 9 个所需组件（button、input、select、checkbox、radio-group、switch、table、card、badge、dialog、tabs、skeleton、textarea）；同时创建 `src/lib/utils.ts` 提供 `cn()` 工具函数（基于 clsx + tailwind-merge），并在 `index.css` 中配置 shadcn 的 CSS 变量主题系统。

**TDesign 集成方式**：`npm install tdesign-react tdesign-icons-react`，在 `main.tsx` 中 `import 'tdesign-react/es/style/index.css'`，按需引入组件和图标，无需额外配置。

### 实施备注

- **无状态管理库**：Demo 为纯展示 + 本地交互（Dialog 开关、Tabs 切换、Toast 触发），使用 React 内置 `useState` 即可，无需引入 Zustand
- **无路由**：单页面应用，无需 React Router
- **组件精简**：shadcn 仅复制展示所需的组件源码，不运行 `npx shadcn-ui` CLI（交互式命令不适合自动化创建）
- **独立目录**：项目放在 `frontend-demo/` 下，与现有 Python 项目完全隔离，后续可随时删除

## 设计风格：专业对比展示

采用**深色顶栏 + 浅灰色背景 + 白色卡片**的专业对比展示风格。左右分栏以中轴线清晰区分两套组件库，每个对比区用标题和卡片承载，视觉层次分明。整体风格克制、专业，让用户聚焦于组件本身的设计差异。

## 单页面设计：组件对比总览

### 区块 1 — 顶部固定导航

深蓝背景 (#1E293B)，高度 56px，固定在页面顶部。左侧白色标题文字"组件库对比 Demo"，右侧两个标签徽标分别标识 TDesign (#0052D9) 和 shadcn/ui (#18181B)。z-index 最高层。

### 区块 2 — 左侧锚点导航

宽度 180px，sticky 定位在导航栏下方。浅灰背景 (#F8FAFC)，5 个分类锚点链接（按钮、表单、数据展示、导航、反馈），当前滚动到的区域高亮显示（左侧蓝色竖条指示）。点击触发 smooth scroll。

### 区块 3 — 按钮对比区

白色卡片，标题"按钮 Button"。两栏各展示按钮矩阵：4 列（Primary/Secondary/Outline/Text 变体）× 3 行（Small/Medium/Large 尺寸），底部独立一行展示 Loading 和 Disabled 状态。每栏上方标注库名。

### 区块 4 — 表单对比区

白色卡片，标题"表单 Form"。两栏各一组表单，垂直排列：Input（带 Label）、Select（3 个下拉选项）、Checkbox 组（3 个勾选项）、Radio 组（3 个单选项）、Switch（开关）、Textarea（文本域）。各控件间距 16px。

### 区块 5 — 数据展示对比区

白色卡片，标题"数据展示 Data Display"。两栏各展示：一张 3 列 4 行的基础 Table（表头加粗、斑马纹行）、一张 Card（含标题、描述文字、操作按钮）、一组多色 Tag（Default/Success/Warning/Danger）。

### 区块 6 — 导航对比区

白色卡片，标题"导航 Navigation"。两栏各展示：一组可点击切换的 Tabs（3 个标签页，切换后下方内容区域变化）、一条 3 级 Breadcrumb（首页 > 模块 > 详情）。

### 区块 7 — 反馈对比区

白色卡片，标题"反馈 Feedback"。两栏各展示：一个"打开对话框"按钮（点击弹出 Dialog，含标题、正文、确认/取消按钮）、一个"显示消息"按钮（点击触发 Toast 消息提示）、一个 Skeleton 骨架屏卡片（模拟加载态）。

### 区块 8 — 页脚

居中灰色文字"组件库对比 Demo · 仅供参考 · 2026"，浅灰背景。

## Agent Extensions

### Skill

- **prototype**
- 用途：构建组件库对比的 throwaway prototype，让用户在实际代码中体验两套组件库的差异
- 预期成果：在 `frontend-demo/` 下生成一个可直接 `npm run dev` 启动的对比页面，左右并排展示五大类组件