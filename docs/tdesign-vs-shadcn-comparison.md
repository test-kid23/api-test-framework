## 产品概述

创建两个独立的前端 Demo 项目，分别在浏览器中打开对比展示。用于帮助开发者在正式启动前端开发前，在 **Vue 3 + TDesign** 和 **React + shadcn/ui** 两套技术方案之间做出选型决策。

## 核心功能

两个项目展示相同场景的组件，各自独立运行：

### 方案 A：Vue 3 + Vite + TDesign Vue Next

- **项目路径**：`frontend-demo/vue-tdesign/`
- **技术栈**：Vue 3 + TypeScript + Vite 5 + TDesign Vue Next + tdesign-icons-vue-next

### 方案 B：React 18 + Vite + shadcn/ui

- **项目路径**：`frontend-demo/react-shadcn/`
- **技术栈**：React 18 + TypeScript + Vite 5 + Tailwind CSS 3 + shadcn/ui

### 两项目共同展示的组件场景

- **按钮区**：Primary / Success / Warning / Danger / Default 五种变体 x S/M/L 三种尺寸 + Loading 与 Disabled 状态
- **表单区**：Input（普通/密码/带清空）、Select、Checkbox 组、Radio 组、Switch、DatePicker、Textarea
- **数据展示区**：Table（带分页）、Card（含图片/标题/描述/按钮）、Tag / Badge 组（多色）
- **导航区**：Tabs（可切换标签页）、Breadcrumb（多级面包屑）、Pagination
- **反馈区**：Dialog/Modal（可触发弹窗）、Toast/Message（可触发消息提示）、Skeleton 骨架屏

### 每个项目页面结构

- 顶部导航（标识"方案 A：Vue 3 + TDesign" / "方案 B：React + shadcn/ui"）
- 左侧分类锚点导航（按钮 -> 表单 -> 数据展示 -> 导航 -> 反馈）
- 右侧主内容区（五大组件分区，白色卡片承载，各分区标题 + 组件展示）
- 底部页脚

## 技术栈

### 方案 A：vue-tdesign

| 项 | 选型 |
| --- | --- |
| 框架 | Vue 3 (Composition API + `<script setup>`) |
| 构建 | Vite 5 |
| 类型 | TypeScript 5 |
| 组件库 | `tdesign-vue-next` + `tdesign-icons-vue-next` |
| CSS | TDesign 自带样式 |


### 方案 B：react-shadcn

| 项 | 选型 |
| --- | --- |
| 框架 | React 18 (函数组件 + Hooks) |
| 构建 | Vite 5 |
| 类型 | TypeScript 5 |
| 组件库 | shadcn/ui（Radix UI 原语，手动复制组件源码） |
| CSS | Tailwind CSS 3.4.17 + shadcn CSS 变量主题 |


## 实现策略

### 项目结构

```
frontend-demo/
├── vue-tdesign/                    # 方案 A
│   ├── src/
│   │   ├── App.vue                 # 主页面，含所有组件展示区
│   │   ├── main.ts                 # 入口，引入 TDesign CSS
│   │   └── style.css               # 全局样式
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
└── react-shadcn/                   # 方案 B
    ├── src/
    │   ├── App.tsx                 # 主页面，含所有组件展示区
    │   ├── main.tsx                # 入口
    │   ├── index.css               # Tailwind + shadcn CSS 变量
    │   ├── lib/
    │   │   └── utils.ts            # cn() 工具函数
    │   └── components/
    │       └── ui/                 # shadcn 组件源码
    │           ├── button.tsx
    │           ├── input.tsx
    │           ├── select.tsx
    │           ├── checkbox.tsx
    │           ├── radio-group.tsx
    │           ├── switch.tsx
    │           ├── textarea.tsx
    │           ├── table.tsx
    │           ├── card.tsx
    │           ├── badge.tsx
    │           ├── tabs.tsx
    │           ├── dialog.tsx
    │           ├── skeleton.tsx
    │           └── sonner.tsx      # Toast
    ├── index.html
    ├── package.json
    ├── postcss.config.js
    ├── tailwind.config.js
    ├── tsconfig.json
    └── vite.config.ts
```

### 方案 A 实现要点 (Vue + TDesign)

- 使用 `npm create vite@5 vue-tdesign -- --template vue-ts` 脚手架
- 安装 `tdesign-vue-next` 和 `tdesign-icons-vue-next`
- 在 `main.ts` 中 `import 'tdesign-vue-next/es/style/index.css'`
- 全量引入 TDesign 组件和图标（Demo 场景无需按需加载）
- 使用 Vue 3 `<script setup>` + Composition API
- 交互状态用 `ref()` 管理（Dialog 开关、Tabs 选中项、Toast 触发等）

### 方案 B 实现要点 (React + shadcn)

- 使用 `npm create vite@5 react-shadcn -- --template react-ts` 脚手架
- 安装 Tailwind CSS 3.4.17 + `tailwind-merge` + `tailwindcss-animate`
- 安装 shadcn 底层依赖：`@radix-ui/*` 系列、`class-variance-authority`、`clsx`、`lucide-react`、`sonner`
- 手动创建 `src/lib/utils.ts` 提供 `cn()` 函数
- `index.css` 中配置 Tailwind 三重指令 + shadcn CSS 变量主题
- 手动复制 shadcn/ui 14 个所需组件源码到 `src/components/ui/`
- 交互状态用 `useState` 管理

### 两个项目的共同实现

- **无路由**：单页面滚动展示
- **无状态管理库**：纯组件内 `useState` / `ref()` 即可
- **锚点导航**：左侧 sticky 导航 + 点击 smooth scroll 到对应区域
- **布局**：固定顶部导航 + 左侧锚点菜单 + 右侧滚动内容区
- **独立运行**：两个项目各自 `npm run dev`，分别在浏览器 Tab 打开对比

### shadcn 组件依赖说明

需复制的 shadcn 组件及底层 Radix 依赖：

- Button、Input、Textarea → 无需额外 Radix 依赖
- Select → `@radix-ui/react-select`
- Checkbox → `@radix-ui/react-checkbox`
- RadioGroup → `@radix-ui/react-radio-group`
- Switch → `@radix-ui/react-switch`
- Table → 无需额外依赖
- Card → 无需额外依赖
- Badge → 无需额外依赖
- Tabs → `@radix-ui/react-tabs`
- Dialog → `@radix-ui/react-dialog`
- Skeleton → 无需额外依赖
- Sonner (Toast) → `sonner` 包

## 设计风格

两个项目各自独立的组件展示页面，采用**深色顶栏 + 浅灰背景 + 白色卡片**的专业风格。左侧 sticky 分类锚点导航，右侧滚动展示五大组件分区。每个分区为白色圆角卡片，内含该方案组件的丰富展示。两个项目虽然技术栈不同，但页面结构和展示组件场景保持一致，方便在不同浏览器 Tab 中对比参考。

### 页面区块（两个项目结构相同）

**区块 1：顶部固定导航**
深蓝/暗色背景，56px 高。左侧项目标识文字（"Vue 3 + TDesign Demo"/"React + shadcn/ui Demo"），右侧标签展示技术栈徽标。

**区块 2：左侧锚点导航**
宽度 180px，sticky 定位。5 个分类链接（按钮/表单/数据展示/导航/反馈），当前滚动区域高亮指示。

**区块 3：按钮展示区**
白色卡片，标题"按钮 Button"。展示多行按钮矩阵：变体列 x 尺寸行，底部展示 Loading/Disabled 特殊状态。

**区块 4：表单展示区**
白色卡片，标题"表单 Form"。垂直排列 8 种表单控件，每种控件带中文 Label，可交互。

**区块 5：数据展示区**
白色卡片，标题"数据展示 Data Display"。包含分页 Table、图文 Card、多色 Tag 组。

**区块 6：导航展示区**
白色卡片，标题"导航 Navigation"。可切换 Tabs + 多级 Breadcrumb + Pagination。

**区块 7：反馈展示区**
白色卡片，标题"反馈 Feedback"。触发式 Dialog + Toast + Skeleton 骨架屏。

**区块 8：页脚**
居中灰色小字，浅灰背景。

## Agent Extensions

### Skill

- **prototype**
- 用途：分别构建两个 throwaway prototype 项目（Vue 3 + TDesign 和 React + shadcn/ui），让用户在实际代码中对比两套方案的开发体验和组件风格
- 预期成果：`frontend-demo/vue-tdesign/` 和 `frontend-demo/react-shadcn/` 两套可分别 `npm run dev` 启动的完整 Demo 项目