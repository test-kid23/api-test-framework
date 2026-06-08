# AutoTest Platform - 管理前端

> React 18 + Vite + shadcn/ui 构建的 API 自动化测试平台管理界面。

## 技术栈

| 类别 | 技术 |
|------|------|
| 框架 | React 18 + TypeScript 5 |
| 构建 | Vite 5 |
| 样式 | Tailwind CSS 3 + shadcn/ui (Radix UI) |
| 状态管理 | Zustand |
| 服务端数据 | TanStack Query (React Query) |
| 路由 | React Router 6 (HashRouter) |
| HTTP | Axios |
| 图表 | Recharts |

## 快速开始

```bash
# 1. 安装依赖
npm install

# 2. 开发模式启动（默认 http://localhost:5173）
npm run dev

# 3. 生产构建（输出到 ../api/static/）
npm run build

# 4. 预览构建产物
npm run preview
```

## 项目结构

```
frontend/
├── public/                  # 静态资源
├── src/
│   ├── api/                 # API 封装层（Axios 实例 + 各资源模块）
│   │   ├── client.ts        #   Axios 实例 (baseURL: /api/v1)
│   │   ├── cases.ts         #   用例 CRUD API
│   │   ├── executions.ts    #   执行触发/查询 API
│   │   ├── reports.ts       #   报告看板 API
│   │   └── environments.ts  #   环境管理 API
│   ├── components/
│   │   ├── layout/          # 布局组件
│   │   │   ├── AppLayout.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Header.tsx
│   │   └── ui/              # shadcn/ui 基础组件
│   ├── hooks/               # TanStack Query hooks
│   │   ├── useCases.ts
│   │   ├── useExecutions.ts
│   │   ├── useReports.ts
│   │   └── useEnvironments.ts
│   ├── lib/                 # 工具函数
│   │   └── utils.ts         #   cn() (clsx + tailwind-merge)
│   ├── pages/               # 页面组件
│   │   ├── CasesPage.tsx            # 用例列表
│   │   ├── CaseEditPage.tsx         # 用例编辑（新建/编辑）
│   │   ├── ExecutionsPage.tsx       # 执行历史
│   │   ├── ExecutionDetailPage.tsx   # 执行详情
│   │   ├── DashboardPage.tsx        # 报告看板
│   │   └── EnvironmentsPage.tsx     # 环境管理
│   ├── router/
│   │   └── index.tsx        # 路由配置
│   ├── store/
│   │   └── appStore.ts      # Zustand 全局状态
│   ├── types/
│   │   └── index.ts         # TypeScript 类型定义
│   ├── App.tsx              # 根组件
│   ├── main.tsx             # 入口
│   └── index.css            # 全局样式 + Tailwind
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── components.json          # shadcn/ui 配置
```

## 路由表

| 路径 | 页面 | 说明 |
|------|------|------|
| `/` | - | 重定向到 `/cases` |
| `/cases` | CasesPage | 用例列表（分页/搜索/筛选） |
| `/cases/new` | CaseEditPage | 新建用例 |
| `/cases/:id/edit` | CaseEditPage | 编辑用例 |
| `/executions` | ExecutionsPage | 执行历史列表 |
| `/executions/:id` | ExecutionDetailPage | 执行详情 |
| `/dashboard` | DashboardPage | 报告看板（图表） |
| `/environments` | EnvironmentsPage | 环境管理 CRUD |

## 开发说明

### 后端代理

开发模式下，Vite 自动将 `/api` 请求代理到 `http://localhost:8000`（见 `vite.config.ts`）。

```bash
# 终端 1：启动后端 API 服务
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 终端 2：启动前端开发服务器
cd frontend && npm run dev
```

### HashRouter

使用 `createHashRouter` 而非 `BrowserRouter`，适配静态部署场景（FastAPI `StaticFiles` 挂载无需服务端路由回退）。

### 构建集成

```bash
npm run build  # 输出到 ../api/static/
```

FastAPI 通过 `StaticFiles` 挂载该目录即可访问前端界面。
