# AutoTest Framework · 前端开发规划

> **制定日期**: 2026-06-08 | **最后更新**: 2026-06-09  
> **关联文档**: [开发计划 v2](./development-plan.md)、[架构评审](./architecture-review.md)  
> **技术栈**: React 18 + TypeScript 5 + Vite 5 + Tailwind 3 + shadcn/ui + Zustand 4 + TanStack Query 5  
> **设计参考**: [shadcn/ui](https://ui.shadcn.com/)、[Radix UI](https://www.radix-ui.com/)、lucide-react icons

---

## 开发进度总览

| Phase | 内容 | 状态 | 完成日期 |
|-------|------|------|----------|
| **Phase A** | 基础设施 + API 对齐 | ✅ 完成 | 2026-06-08 |
| **Phase B** | 核心页面重构 (7 个页面) | ✅ 完成 | 2026-06-09 |
| **Phase C** | 新页面开发 (5 个页面) | ✅ 完成 | 2026-06-09 |
| **Phase D** | 细节打磨（动画/空态/响应式/暗色/骨架） | ✅ 完成 | 2026-06-09 |

> **当前状态**: 全部 4 个 Phase 已完成，11 个业务页面就绪，34 个 shadcn/ui 组件集成，`tsc --noEmit` 零错误。

---

## 目录

1. [当前状态评估](#1-当前状态评估)
2. [设计体系基础](#2-设计体系基础)
3. [API 对齐与类型修正](#3-api-对齐与类型修正)
4. [需要新增的 shadcn/ui 组件](#4-需要新增的-shadcnui-组件)
5. [页面重构计划](#5-页面重构计划)
6. [新增页面计划](#6-新增页面计划)
7. [全局 Layout 优化](#7-全局-layout-优化)
8. [实现分阶段规划](#8-实现分阶段规划)
9. [视觉设计规范](#9-视觉设计规范)
10. [前端技术特点](#10-前端技术特点)

---

## 1. 当前状态评估

### 1.1 已完成（Phase D 之后）

| 模块 | 状态 | 说明 |
|------|------|------|
| 项目脚手架 | ✅ 完成 | Vite + React 18 + TypeScript + shadcn/ui + Tailwind |
| 基础组件库 | ✅ 完成 | 34 个 shadcn/ui 组件 + 2 个自定义组件 (StatusBadge, EmptyState) |
| 路由系统 | ✅ 完成 | react-router-dom v6 Hash 路由，11 条路由 |
| API 服务层 | ✅ 完成 | axios 客户端 + 7 个 API 模块 (cases/suites/executions/environments/schedules/reports/client) |
| 状态管理 | ✅ 完成 | Zustand (UI 状态含主题切换) + TanStack Query (6 个自定义 hooks) |
| CasesPage | ✅ 完成 | 列表 + ⌘K 搜索 + Tab 筛选 + 批量操作 + Pagination + 导入入口 |
| CaseEditPage | ✅ 完成 | 左右分栏 + TagInput + YAML 行号预览 + 校验/格式化 + Toast |
| CaseDetailPage | ✅ 完成 | 只读详情 + 版本历史 + 最近执行摘要 |
| CaseImportPage | ✅ 完成 | OpenAPI URL 解析 + 接口勾选 + 导入结果反馈 |
| ExecutionsPage | ✅ 完成 | 触发执行 Sheet + 状态列进度条 + 自动刷新脉冲动画 |
| ExecutionDetailPage | ✅ 完成 | Accordion 步骤详情 + Progress 通过率条 + 耗时统计 |
| DashboardPage | ✅ 完成 | 5 KPI 指标卡 + CSS 变量配色图表 + 水平进度条 + Skeleton 占位 |
| EnvironmentsPage | ✅ 完成 | 卡片网格布局 + 变量编辑 (Key-Value 表格) + 当前环境高亮 |
| SuitesPage | ✅ 完成 | 套件 CRUD + 关联用例选择 + 卡片网格 + 一键执行 |
| SchedulesPage | ✅ 完成 | 调度 CRUD + Cron 快捷选项 + 下次执行预览 + Switch 开关 |
| ReportsPage | ✅ 完成 | 报告列表 + 环境筛选 + 报告详情 |
| 全局 Layout | ✅ 完成 | Sidebar 分组 + Header ⌘K + 环境切换 + 面包屑 + 暗色模式切换 |
| 细节打磨 | ✅ 完成 | 页面过渡动画 + 列表项 hover + EmptyState 统一 + 响应式 Mobile Sheet + 暗色全适配 + 各页面定制 Skeleton |

### 1.2 已解决的问题（Phase A-D）

> 以下问题已全部在四轮迭代中修复，仅保留作为设计决策记录。

**功能完整性** ✅
- ~~Suites/Schedules 前端缺失~~ → Phase C 完成 SuitesPage + SchedulesPage 开发
- ~~OpenAPI 导入入口缺失~~ → Phase C 完成 CaseImportPage
- ~~Worker 执行状态未对接~~ → Phase A 新增 `useExecutionStatus` hook (3s 轮询)
- ~~Environments 变量管理缺失~~ → Phase B 完成 Key-Value 变量编辑表格
- ~~Execution 触发交互缺失~~ → Phase B 完成套件/环境选择 Sheet

**视觉效果** ✅
- ~~统一的 Card 包装模式~~ → Phase B 各页面采用差异化布局（Tab 筛选、卡片网格、左右分栏）
- ~~表格信息密度低~~ → Phase B 扩展表格列，丰富信息密度
- ~~图表硬编码配色~~ → Phase B 全部图表映射到 `--chart-1~5` CSS 变量
- ~~缺少微交互~~ → Phase D 添加页面过渡动画、hover 反馈、Skeleton 骨架
- ~~Header/Sidebar 简单~~ → Phase A 完成分组导航、⌘K 搜索、环境切换、主题切换

**数据一致性** ✅
- ~~Dashboard 端点不一致~~ → Phase A 拆分为 `usePassRateTrend` + `useTopFailures`
- ~~Execution 类型字段名不一致~~ → Phase A 修正为 `name` + `summary` 结构
- ~~Environment.variable_count~~ → Phase A 修正为 `variables: Record<string, string>`

---

## 2. 设计体系基础

### 2.1 现有设计 Token（无需修改）

项目已通过 shadcn/ui CSS Variables 定义了完整的设计系统：

| Token | 值 | 用途 |
|-------|-----|------|
| `--primary` | `221.2 83.2% 53.3%` | 主色调（蓝色系） |
| `--secondary` | `210 40% 96.1%` | 次级色（浅灰） |
| `--muted` | `210 40% 96.1%` | 弱化文本/背景 |
| `--destructive` | `0 84.2% 60.2%` | 危险操作 |
| `--border` | `214.3 31.8% 91.4%` | 边框 |
| `--ring` | `221.2 83.2% 53.3%` | 聚焦环 |
| `--radius` | `0.5rem` | 圆角基准 |
| `--background` | `0 0% 100%` | 页面背景 |
| `--foreground` | `222.2 84% 4.9%` | 前景文本 |

支持 `dark` 模式完整切换。**现有 token 体系良好，无需重新定义。**

### 2.2 设计原则（遵循 design-workflow skill）

四条核心原则：

1. **使用已有设计系统** — 全部组件必须引用 CSS 变量，禁止硬编码颜色值。图表配色改用 HSL 变量映射
2. **避免 AI 通病** — 禁止紫色渐变、完全居中布局、千篇一律的三列卡片。用非对称布局、差异化卡片尺寸制造节奏
3. **按组件逐层构建** — Button → Badge → Card → 复合 → 页面，每一步先独立验证
4. **真数据真内容** — 去掉 "Lorem ipsum" 和 Mock 占位，所有空态/加载态使用真实业务数据

### 2.3 状态色映射（用于 Badge / 状态标签 / 图表）

```typescript
const statusColors = {
  // 执行状态
  PASSED:  "bg-emerald-50 text-emerald-700 border-emerald-200",   // 通过
  FAILED:  "bg-red-50 text-red-700 border-red-200",               // 失败  
  RUNNING: "bg-blue-50 text-blue-700 border-blue-200",            // 运行中
  PENDING: "bg-amber-50 text-amber-700 border-amber-200",         // 等待
  CANCELLED: "bg-slate-50 text-slate-500 border-slate-200",      // 已取消
  ERROR:   "bg-red-50 text-red-700 border-red-200",               // 错误
  
  // 优先级
  P0: "bg-red-50 text-red-700 border-red-200",
  P1: "bg-orange-50 text-orange-700 border-orange-200",
  P2: "bg-blue-50 text-blue-700 border-blue-200",
  P3: "bg-slate-50 text-slate-500 border-slate-200",
};
```

### 2.4 新增 shadcn/ui 颜色 Token 建议

当前项目仅有 `default`/`destructive`/`secondary`/`outline`/`ghost` Badge 变体。建议为状态色增加自定义 Badge variant（通过 `class-variance-authority` 扩展），使状态展示语义化更强。

---

## 3. API 对齐与类型修正

### 3.1 前端类型重定义（`src/types/index.ts`）

**当前问题**：前端类型与后端 Schema 不一致，导致运行时数据访问错误。必须在开发新页面前完成类型修正。

```typescript
// === 修正前 (当前) ===
export interface Execution {
  suite_name: string;       // ❌ 后端字段是 name
  total_cases: number;      // ❌ 后端在 summary 字典中
  passed_cases: number;     // ❌ 同上
  failed_cases: number;     // ❌ 同上
}

// === 修正后 ===
export interface Execution {
  id: string;
  name: string;                      // ← 修正
  status: ExecutionStatus;
  trigger: ExecutionTrigger;
  env_name: string;
  started_at: string;
  finished_at: string | null;
  summary: ExecutionSummary;         // ← 新增
  celery_task_id: string | null;
  created_at: string;
}

export interface ExecutionSummary {
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  error_cases: number;
}

export interface Environment {
  id: string;
  name: string;
  description: string;
  base_url: string;
  ws_url?: string;
  variables: Record<string, string>;  // ← 修正（原是 variable_count: number）
  created_at: string;
  updated_at: string;
}
```

### 3.2 API 路径修正

| 模块 | 当前前端调用 | 实际后端端点 | 修正方向 |
|------|-------------|-------------|---------|
| Reports | `GET /reports/dashboard` | `GET /reports/trends` + `GET /reports/top-failures` | 前端拆分为 2 个独立 hook |
| Cases | 缺少 import | `POST /cases/import` | 新增 `casesApi.importFromUrl()` |
| Executions | 缺少 status 轮询 | `GET /executions/{id}/status` | 新增 `executionStatus` hook |
| Schedules | 完全缺失 | 6 个端点 | 新增完整 API 模块 |
| Suites | 完全缺失 | 5 个端点 | 新增完整 API 模块 |

### 3.3 React Query Hooks 调整

```typescript
// 新增: hooks/useSuites.ts
export function useSuites(params: {...}) { ... }
export function useCreateSuite() { ... }
export function useUpdateSuite() { ... }
export function useDeleteSuite() { ... }

// 新增: hooks/useSchedules.ts
export function useSchedules(params: {...}) { ... }
export function useCreateSchedule() { ... }
export function useUpdateSchedule() { ... }
export function useDeleteSchedule() { ... }
export function useRunSchedule() { ... }

// 修正: hooks/useReports.ts
export function usePassRateTrend(days: number) { ... }   // GET /reports/trends
export function useTopFailures(limit: number) { ... }     // GET /reports/top-failures
```

---

## 4. 需要新增的 shadcn/ui 组件

当前已集成 12 个 shadcn/ui 组件，以下为各页面需要的额外组件：

### 4.1 全局使用

| 组件 | 用途 | Radix 依赖 |
|------|------|-----------|
| **Tooltip** | 图标按钮提示、截断文本悬浮完整内容 | `@radix-ui/react-tooltip` |
| **Toast (Sonner)** | 操作结果通知（创建成功/删除成功/错误提示） | `sonner` (推荐替代) |
| **Separator** | 内容区分隔线 | `@radix-ui/react-separator` |
| **Avatar** | Header 用户头像 | `@radix-ui/react-avatar` |

### 4.2 页面专用

| 组件 | 使用页面 | 用途 |
|------|---------|------|
| **Accordion** | ExecutionDetail | 折叠展开每条用例的详细步骤 |
| **Progress** | ExecutionDetail, Dashboard | 测试进度条、通过率环形展示 |
| **ScrollArea** | CaseEdit (YAML编辑区) | 大段 YAML/JSON 可滚动区域 |
| **Command (cmdk)** | Cases, 全局搜索 | ⌘K 命令面板 + 快速搜索 |
| **Popover** | CaseEdit, Environments | 日期选择、变量编辑浮层 |
| **HoverCard** | Cases, Executions | 用例/执行预览卡片 |
| **Switch** | Schedules | 调度开关（启用/停用） |
| **RadioGroup** | CaseEdit | 触发方式/优先级选择 |
| **Alert / AlertDialog** | 全局 | 危险操作确认（替换当前基础 Dialog） |
| **Breadcrumb** | 全局 | 页面导航面包屑 |
| **Sheet** | 全局 | 移动端侧边栏抽屉 |
| **Calendar** | Schedules | cron 表达式预览日期 |
| **Slider** | Dashboard | 时间范围滑块 |
| **Carousel** | Dashboard | 报告概览卡片轮播（可选） |
| **Pagination** | Cases, Executions | 替换当前手动分页按钮 |

### 4.3 安装命令

```bash
cd frontend
npx shadcn@latest add tooltip sonner separator avatar \
  accordion progress scroll-area command popover \
  hover-card switch radio-group alert-dialog \
  breadcrumb sheet calendar slider pagination
```

---

## 5. 页面重构计划

### 5.1 CasesPage（用例管理）— 优先级 P0

**当前问题**：
- 表格仅 5 列，大量水平空间浪费
- 搜索和筛选分散在两个 Card 中，占用过多垂直空间
- 分页为手动上下页按钮，不够直观
- 缺少批量操作（批量删除、批量执行）

**重构方案**：

```
┌─────────────────────────────────────────────────────────┐
│ [搜索框 (占满宽度, ⌘K 唤起)]           [从 OpenAPI 导入] [新建用例] │
├─────────────────────────────────────────────────────────┤
│ 全部(42)  P0(3)  P1(8)  P2(15)  P3(16)     [标签筛选 ▼] │  ← 横向 Tab 筛选
├─────────────────────────────────────────────────────────┤
│  ☐ │ 用例名称           │ 标签   │ 优先级 │ 所属套件 │ 更新 │ 操作 │
│    │ 用户登录接口验证     │ smoke  │ P0     │ 核心用例 │ 2h前 │ ⋯   │
│    │ 订单列表分页测试     │ paging │ P2     │ -       │ 1d前 │ ⋯   │
│ ...                                                       │
├─────────────────────────────────────────────────────────┤
│ 已选 3 项  [批量执行] [批量删除]    第 1-15/共 42   ← 1 2 3 → │
└─────────────────────────────────────────────────────────┘
```

**关键改进**：
- 搜索框集成 `⌘K` 命令面板（Command 组件），支持快捷键全局搜索
- 顶部使用横向 Tab（优先级数量统计）替代下拉筛选，视觉更紧凑
- 表格新增「所属套件」列和「更新时间」列
- 支持行选择（checkbox），提供批量执行/批量删除
- 使用 shadcn Pagination 组件替代手动按钮
- 新增「从 OpenAPI 导入」按钮，跳转到导入页（见 6.2）

### 5.2 CaseEditPage（用例编辑）— 优先级 P0

**当前问题**：
- 仅 4 个字段，缺描述、套件关联、请求预览
- YAML textarea 无语法高亮、无行号、无校验提示
- 保存后无 Toast 通知

**重构方案**：

```
┌──────────────────────────────────────────────────────────┐
│ ← 返回列表              新建用例 / 编辑用例              │
├──────────────────────┬───────────────────────────────────┤
│ 基本信息              │                                   │
│                      │  ┌─ YAML 编辑区 ──────────────┐  │
│  用例名称 [________] │  │ 1  name: 用户登录验证      │  │
│                      │  │ 2  steps:                  │  │
│  描述     [________] │  │ 3    - request:            │  │
│                      │  │ 4        method: POST       │  │
│  优先级   ○ P0 ○ P1  │  │ ...                  400px │  │
│           ○ P2 ○ P3  │  │                            │  │
│                      │  └────────────────────────────┘  │
│  标签     [smoke ×]  │                                   │
│          [+ 添加]    │  ┌─ 请求预览 ──────────────────┐  │
│                      │  │ POST /api/auth/login        │  │
│  所属套件 [核心用例 ▼]│  │ Headers: Content-Type: json │  │
│                      │  │ Body: {"user":"admin"}       │  │
│                      │  └────────────────────────────┘  │
│                      │                                   │
│  ─────────────────── │  ──────────────────────────────   │
│  [保存] [取消]       │  [格式化YAML] [校验语法]          │
└──────────────────────┴───────────────────────────────────┘
```

**关键改进**：
- 左右分栏：左侧表单（基本信息），右侧 YAML 编辑 + 实时预览
- 新增「描述」字段
- 新增「所属套件」下拉关联
- 标签输入改为 Tag Input（自由输入 + 回车确认 + × 删除）
- YAML 编辑区加入行号（CSS counter），添加「格式化」和「校验」按钮
- 保存/取消按钮吸底，面包屑返回
- 保存成功后 Toast "用例已保存"

### 5.3 ExecutionsPage（执行历史）— 优先级 P1

**当前问题**：
- 表格列缺失（未展示通过/失败数）
- 自动刷新无视觉指示器
- 缺少执行触发入口

**重构方案**：

```
┌──────────────────────────────────────────────────────────┐
│ ⏱ 自动刷新中              执行历史          [触发新执行] │
├──────────────────────────────────────────────────────────┤
│ 全部  通过  失败  运行中  等待                            │
├──────────────────────────────────────────────────────────┤
│ 执行名称          │ 状态 │ 通过/失败 │ 触发 │ 耗时  │ 时间 │
│ 核心API冒烟测试    │ ✓ 通过│ 12/12    │ 定时 │ 2.3s │ 10:30 │
│ 用户模块回归测试   │ ✗ 失败│ 38/42    │ 手动 │ 45s  │ 09:15 │
│ 订单模块 CI 测试   │ ◌ 运行│ 5/20     │ Webhook│ -  │ 10:32 │
│ ...                                                        │
├──────────────────────────────────────────────────────────┤
│                                                       1 2 3 → │
└──────────────────────────────────────────────────────────┘
```

**关键改进**：
- 顶部添加「触发新执行」按钮，弹出 Sheet/Dialog 选择套件+环境
- 自动刷新时标题旁显示脉冲动画指示器
- 表格新增「通过/失败」列（如 `12/12` 全绿、`38/42` 红+绿）
- 使用 Progress 组件在运行中的行内嵌进度条
- 行 hover 时显示快捷操作（查看报告/重新执行/取消）

### 5.4 ExecutionDetailPage（执行详情）— 优先级 P1

**当前问题**：
- 摘要卡片信息密度低
- 未展示每个用例的详细步骤结果
- 缺少步骤级请求/响应对比

**重构方案**：

```
┌──────────────────────────────────────────────────────────┐
│ ← 返回列表    核心API冒烟测试                          │
├──────────────────────────────────────────────────────────┤
│ ┌────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐          │
│ │ 97.5%  │ │ 42     │ │ 开发环境  │ │ ✓ 已完成  │          │
│ │ 通过率  │ │ 总用例  │ │ ENV     │ │ 状态     │          │
│ └────────┘ └────────┘ └─────────┘ └──────────┘          │
│                                                          │
│ ████████████████████████████████░░ 97.5% (39 通过, 1 失败)│
├──────────────────────────────────────────────────────────┤
│ 用例结果 (42)                            [仅看失败] [展开全部]│
├──────────────────────────────────────────────────────────┤
│ ▼ ✓ 用户登录接口验证                    2.3s   ✓ 通过    │  ← Accordion
│   ┌─ 步骤 1: POST /api/auth/login ──────────────────┐   │
│   │  请求: POST /api/auth/login  Status: 200          │   │
│   │  响应: {"token":"xxx","user":{...}}   ✓ 断言通过   │   │
│   └──────────────────────────────────────────────────┘   │
│                                                          │
│ ▶ ✓ 获取用户信息                        1.1s   ✓ 通过    │
│                                                                        
│ ▼ ✗ 订单创建接口                       5.2s   ✗ 失败    │
│   ┌─ 步骤 1: POST /api/orders ──────────────────────┐   │
│   │  请求: POST /api/orders  Status: 500             │   │
│   │  错误: status_code expected 201, got 500         │   │
│   │  Response: {"error":"Internal Server Error"}     │   │
│   └──────────────────────────────────────────────────┘   │
├──────────────────────────────────────────────────────────┤
│ 耗时分布: 平均 2.1s  P50 1.8s  P95 5.2s  P99 5.2s     │
└──────────────────────────────────────────────────────────┘
```

**关键改进**：
- 4 个摘要卡片改为横向平铺（等宽），下方增加 Progress 进度条直观展示通过率
- 用例结果使用 Accordion 组件，折叠/展开查看步骤详情
- 每个步骤展示 HTTP 请求/响应摘要（method + url + status + 断言结果）
- 失败用例自动展开，请求/响应差异高亮
- 顶部添加耗时统计（平均/P50/P95/P99）
- 支持「仅看失败」和「展开/折叠全部」快捷操作

### 5.5 DashboardPage（报告看板）— 优先级 P1

**当前问题**：
- 图表布局简单（2 列 grid），信息密度低
- Mock 数据与应用主题色不匹配
- 缺少概览指标卡片

**重构方案**：

```
┌──────────────────────────────────────────────────────────┐
│ 报告看板                         最近 30 天 ▼   [刷新]   │
├──────────┬──────────┬──────────┬──────────┬──────────────┤
│ 执行次数  │ 总通过率  │ 失败用例  │ 活跃套件  │ 平均耗时     │
│   1,247   │  94.2%   │   72     │    8     │   3.2s      │
│  ↑12% 较上周│ ↑2.1%   │ ↓15%    │  持平    │ ↓8% 较上周   │
├──────────┴──────────┴──────────┴──────────┴──────────────┤
│ ┌──────────────────────┐  ┌─────────────────────────────┐│
│ │  通过率趋势 (折线图)  │  │  失败原因分类 (玫瑰图)      ││
│ │  面积填充 + 均值线   │  │  文字标签 + 中心总数        ││
│ └──────────────────────┘  └─────────────────────────────┘│
│ ┌───────────────────────────────────────────────────────┐ │
│ │  Top 10 不稳定接口                           [查看全部]│ │
│ │  #1 [████████████████████░░░] 用户登录接口    23次     │ │
│ │  #2 [███████████░░░░░░░░░░░░] 订单创建接口    15次     │ │
│ │  ...                                                  │ │
│ └───────────────────────────────────────────────────────┘ │
│ ┌──────────────────────┐  ┌────────────────────────────┐ │
│ │  执行耗时分布 (柱状图)│  │  套件通过率对比 (雷达图)   │ │
│ └──────────────────────┘  └────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

**关键改进**：
- 顶部增加 5 个 KPI 指标卡片（含环比变化 + 趋势箭头）
- 失败原因改用带文字标签的饼图/玫瑰图（中心显示总数）
- Top N 不稳定接口用水平进度条展示相对数量
- 新增执行耗时分布柱状图、套件通过率对比图
- 图表配色全部使用 CSS 变量映射，移除硬编码 `COLORS` 数组
- 移除 Mock 数据，API 未就绪时展示 Skeleton 占位（不用假数据误导）

### 5.6 EnvironmentsPage（环境管理）— 优先级 P1

**当前问题**：
- 变量管理完全缺失（仅展示数量）
- 创建/编辑弹窗无变量输入

**重构方案**：

```
┌──────────────────────────────────────────────────────────┐
│ 环境管理                                    [新建环境]   │
├──────────────────────────────────────────────────────────┤
│ ┌─────────────────────┐ ┌─────────────────────┐          │
│ │ ● 开发环境  (当前)   │ │   测试环境           │          │
│ │                     │ │                     │          │
│ │ base_url:           │ │ base_url:           │          │
│ │ http://dev:8080     │ │ http://test:8080    │          │
│ │                     │ │                     │          │
│ │ 变量: 5 配置         │ │ 变量: 8 配置         │          │
│ │ 创建: 2026-05-01    │ │ 创建: 2026-06-01    │          │
│ │ [编辑] [设为当前]    │ │ [编辑] [删除]       │          │
│ └─────────────────────┘ └─────────────────────┘          │
│                                                          │
│ ┌─────────────────────┐ ┌─────────────────────┐          │
│ │   预发布环境         │ │   生产环境           │          │
│ │   ...               │ │   ...               │          │
│ └─────────────────────┘ └─────────────────────┘          │
└──────────────────────────────────────────────────────────┘
```

**关键改进**：
- 表格改为卡片网格布局（2 列），每个环境一张卡片
- 卡片内展示 base_url、变量数量等关键信息
- 编辑弹窗新增「环境变量」表格（Key-Value 键值对，支持动态增减行）
- 支持「设为当前环境」快捷操作
- 当前使用的环境卡片有视觉高亮（primary 边框 + ● 标识）

---

## 6. 新增页面计划

### 6.1 SuitesPage（套件管理）— 优先级 P0（全新开发）

后端 API：`GET/POST /api/v1/suites`、`GET/PUT/DELETE /api/v1/suites/{id}`

**页面功能**：
- 套件列表（卡片网格布局，含名称/描述/包含用例数/状态）
- 创建套件（名称、描述、批量勾选关联用例）
- 编辑套件（修改名称/描述/增减用例关联）
- 删除套件（AlertDialog 二次确认）
- 从套件一键触发执行

```
┌──────────────────────────────────────────────────────────┐
│ 套件管理                                              [新建] │
├──────────────────────────────────────────────────────────┤
│ ┌─────────────────────┐ ┌─────────────────────┐          │
│ │ 核心API冒烟测试      │ │ 用户模块回归测试     │          │
│ │ 覆盖核心登录/支付接口 │ │ 覆盖用户CRUD全流程   │          │
│ │ 包含 12 个用例       │ │ 包含 8 个用例       │          │
│ │ [触发执行] [编辑]    │ │ [触发执行] [编辑]    │          │
│ └─────────────────────┘ └─────────────────────┘          │
└──────────────────────────────────────────────────────────┘
```

### 6.2 CaseImportPage（导入用例）— 优先级 P1（全新开发）

后端 API：`POST /api/v1/cases/import`

**页面功能**：
- 输入 OpenAPI 3.x spec URL
- 预览导入的接口列表（勾选要导入的接口）
- 选择目标套件（可选）
- 导入结果反馈（成功 X 条，失败 Y 条，失败原因）

```
┌──────────────────────────────────────────────────────────┐
│ ← 返回  从 OpenAPI 导入用例                              │
├──────────────────────────────────────────────────────────┤
│ OpenAPI Spec URL: [https://api.example.com/openapi.json] │
│                                                          │
│ [解析]                                                   │
│                                                          │
│ ┌──────────────────────────────────────────────────────┐ │
│ │ 解析到 23 个接口:                全选 ☐  导入到 [核心用例 ▼]│
│ ├──────────────────────────────────────────────────────┤ │
│ │ ☑ POST  /api/auth/login    用户登录                  │ │
│ │ ☑ POST  /api/auth/logout   用户登出                  │ │
│ │ ☑ GET   /api/users         获取用户列表              │ │
│ │ ☐ GET   /api/users/{id}    获取用户详情              │ │
│ │ ...                                                  │ │
│ └──────────────────────────────────────────────────────┘ │
│                                              [开始导入] │
└──────────────────────────────────────────────────────────┘
```

### 6.3 SchedulesPage（调度管理）— 优先级 P1（全新开发）

后端 API：`GET/POST /api/v1/schedules`、`GET/PUT/DELETE /api/v1/schedules/{id}`、`POST /api/v1/schedules/{id}/run`

**页面功能**：
- 调度列表（名称/关联套件/Cron 表达式/下次执行时间/启用状态）
- 创建/编辑调度
  - 选择套件
  - 输入 Cron 表达式（提供快捷选项：每小时/每天/每周/自定义）
  - 实时预览下次 3 次执行时间（Calendar 组件）
- Switch 开关控制启用/停用
- 手动触发一次（立即执行）

```
┌──────────────────────────────────────────────────────────┐
│ 定时调度                                    [新建调度]   │
├──────────────────────────────────────────────────────────┤
│ 名称              │ 套件      │ Cron          │ 下次运行 │ 状态 │
│ 每日冒烟测试       │ 冒烟套件   │ 0 9 * * *     │ 明天09:00│ ● 启用│
│ 周回归测试         │ 全量套件   │ 0 2 * * 1     │ 下周一   │ ○ 停用│
│ ────────────────────────────────────────────────────────────────── │
│                                                          │
│ 创建/编辑调度弹窗:                                        │
│ ┌───────────────────────────────────────────────────┐    │
│ │ 名称: [每日冒烟测试                ]              │    │
│ │ 套件: [核心API冒烟测试          ▼  ]              │    │
│ │ 环境: [开发环境                  ▼  ]              │    │
│ │                                                   │    │
│ │ Cron:  [0 9 * * *           ]                    │    │
│ │        快捷: [每小时] [每天09:00] [每周一] [自定义]│    │
│ │                                                   │    │
│ │ 下次执行: 2026-06-09 09:00 (周一)                 │    │
│ │ 再下次:   2026-06-10 09:00 (周二)                 │    │
│ │ 再下次:   2026-06-11 09:00 (周三)                 │    │
│ │                                                   │    │
│ │ 启用: [Switch ON]                                 │    │
│ │                         [保存] [取消]             │    │
│ └───────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────┘
```

### 6.4 CaseDetailPage（用例详情）— 优先级 P2

**页面功能**：
- 用例基本信息（名称、描述、标签、优先级、所属套件、版本号）
- YAML 内容只读展示（带语法高亮的代码块）
- 版本历史列表
- 最近 5 次执行结果摘要
- 快捷操作：编辑、执行、复制、导出

### 6.5 ReportsPage（报告列表）— 优先级 P2

后端 API：`GET /api/v1/reports`、`GET /api/v1/reports/{id}`

**页面功能**：
- 报告列表（含通过率、总用例、耗时、生成时间）
- 点击进入报告详情页
- 支持按环境筛选

---

## 7. 全局 Layout 优化

### 7.1 当前 Layout 问题

- Sidebar 过于朴素，缺少品牌感
- Header 仅一个折叠按钮 + 下拉菜单，内容空洞
- 缺少面包屑导航
- 缺少全局 Toast 容器

### 7.2 优化方案

**Sidebar 改进**：
```
┌──────────────────┐
│ ■ AutoTest       │  ← Logo 区（图标 + 产品名 + 版本号）
│──────────────────│
│ ── 测试管理 ──    │  ← Section 标题（仅展开态显示）
│ 📋 用例管理       │
│ 📦 套件管理       │  ← 新增
│ ▶  执行历史       │
│──────────────────│
│ ── 数据分析 ──    │
│ 📊 报告看板       │
│ ─────────────────│
│ ── 系统设置 ──    │
│ ⚙  环境管理       │
│ ⏰ 定时调度       │  ← 新增
│──────────────────│
│                  │
│ 收缩/展开  [◀]   │  ← 底部折叠按钮
└──────────────────┘
```

**Header 改进**：
```
┌──────────────────────────────────────────────────────────┐
│ ☰  ⌘K 搜索用例/套件/执行...          当前环境: 开发 ▼  👤 管理员 │
└──────────────────────────────────────────────────────────┘
```

- 增加全局搜索（⌘K Command 组件）
- 环境切换器（从 Zustand store 读取，支持切换）
- 用户头像 + 下拉（Avatar 组件）

### 7.3 全局组件

**Toast 容器**：在 `AppLayout` 中挂载 `<Toaster />`（sonner），所有 mutation 成功后调用 `toast.success()`。

**Breadcrumb**：每个页面顶部自动生成面包屑（通过 `useLocation` 解析路径）。

---

## 8. 实现分阶段规划

### Phase A：基础设施 + API 对齐 ✅ 已完成

**目标**：修复类型不一致、补全 API 模块、安装新组件

| 任务 | 详细内容 | 实施要点 |
|------|---------|---------|
| A1. 类型修正 | 修正 `Execution`、`Environment`、`DashboardData` 类型定义 | `Execution` 新增 `summary` 子对象，`Environment.variables` 改为 `Record<string, string>` |
| A2. 新增 API 模块 | `api/suites.ts`、`api/schedules.ts`、补充 `api/cases.ts`(import)、`api/executions.ts`(status) | 新增 3 个模块，补充 2 个端点，总计 7 个 API 文件 |
| A3. 新增 Hooks | `useSuites.ts`、`useSchedules.ts`、修正 `useReports.ts` | 拆分为 `usePassRateTrend` + `useTopFailures`；新增 `useExecutionStatus` |
| A4. 安装组件 | 执行 `npx shadcn@latest add` 安装第 4 节列出的所有组件 | 安装 22 个新组件，总计 34 个 shadcn/ui 组件 |
| A5. Layout 优化 | Sidebar 分组 + 新增导航项 / Header 搜索 + 环境切换 / 全局 Toast | Sidebar 分 3 组（测试管理/数据分析/系统设置），Header 新增 ⌘K 搜索 + 环境下拉 + Toaster 挂载 |
| A6. 基础组件扩展 | 状态色 Badge 变体、TagInput 组件、EmptyState 组件 | `StatusBadge` 支持 6 种执行状态 + 4 种优先级；`EmptyState` 支持自定义图标和操作按钮 |

### Phase B：核心页面重构 ✅ 已完成

**目标**：全部现有 7 个页面的 UI 重构

| 任务 | 详细内容 | 实施要点 |
|------|---------|---------|
| B1. CasesPage 重构 | ⌘K 搜索、Tab 筛选、批量操作、Pagination 组件、套件列 | 8 列表格（checkbox/名称+描述/标签/优先级/套件/版本/更新时间/操作），横向 Tab 筛选，批量删除按钮 |
| B2. CaseEditPage 重构 | 左右分栏、TagInput、YAML 行号预览、校验/格式化按钮、Toast 通知 | 左侧表单（名称/描述/优先级/标签/套件），右侧 YAML 编辑区 + 请求预览，吸底保存按钮 |
| B3. ExecutionsPage 重构 | 触发执行入口、状态列进度条、自动刷新脉冲动画 | 新增「触发新执行」Sheet（选套件+环境），运行中行内嵌 Progress 条，自动刷新指示器 |
| B4. ExecutionDetailPage 重构 | Accordion 步骤详情、Progress 通过率条、耗时统计 | 4 KPI 卡片 + 通过率进度条 + Accordion 展开步骤级请求/响应，失败用例自动展开 |
| B5. DashboardPage 重构 | KPI 卡片、水平进度条、CSS 变量配色、移除 Mock | 5 列 KPI（含环比箭头），2×2 图表布局 + 底部全宽 Top N 水平进度条，图表配色全部映射 CSS 变量 |
| B6. EnvironmentsPage 重构 | 卡片网格、变量编辑（Key-Value 表格）、当前环境高亮 | 2 列卡片网格，编辑弹窗含动态 Key-Value 变量表格，当前环境 primary 边框 + ● 标识 |
| B7. ReportsPage 重构 | 报告列表 + 环境筛选 + 报告详情 | 8 列表格（名称/环境/状态/通过率/通过/失败/错误/时间），状态 Badge + 通过率百分比 |

### Phase C：新页面开发 ✅ 已完成

**目标**：补齐缺失的 5 个页面

| 任务 | 详细内容 | 实施要点 |
|------|---------|---------|
| C1. SuitesPage | 套件 CRUD + 关联用例选择 + 一键执行 | 卡片网格（2/3 列），每张卡片含名称/描述/用例数/标签，Footer 操作按钮（执行/编辑/删除） |
| C2. CaseImportPage | OpenAPI URL 输入 + 接口勾选列表 + 导入结果 | URL 输入 → 解析 → 接口勾选表格（全选支持）→ 选择目标套件 → 导入结果反馈 |
| C3. SchedulesPage | 调度 CRUD + Cron 快捷选项 + 下次执行预览 + Switch 开关 | 表格含名称/套件/Cron/下次执行/启用状态；编辑弹窗含快捷 Cron 按钮 + 下次 3 次执行时间预览 |
| C4. CaseDetailPage | 只读详情 + 版本历史 + 最近执行摘要 | 卡片式详情（基本信息/YAML 只读/版本历史表格/最近 5 次执行结果），快捷操作（编辑/执行/复制） |
| C5. ReportsPage | 报告列表 + 报告详情（可复用 Dashboard 图表组件） | 环境筛选下拉 + 报告列表表格；点击进入报告详情（复用 Dashboard 的通过率趋势图 + Top Failures 列表） |

### Phase D：细节打磨 ✅ 已完成

**目标**：微交互、响应式、暗色模式兼容

| 任务 | 详细内容 | 实施要点 |
|------|---------|---------|
| D1. 过渡动画 | 页面切换动画、列表项 hover 效果、Dialog 进入/退出动画 | CSS `@keyframes page-fade-in`（opacity + translateY 8px）；`tr { transition: background-color 150ms }`；卡片 `.card-hover` lift 效果 |
| D2. 空态设计 | 每个页面自定义 EmptyState（用例/套件/执行/调度 4 种空态） | `EmptyState` 增强支持自定义 action 图标；6 个页面统一替换，含操作引导按钮 |
| D3. 响应式 | 768px 以下 Sidebar 收为 Sheet 抽屉、表格改为卡片列表 | `md:` 以下隐藏 Sidebar，Header 新增汉堡菜单打开 Sheet；`sm:` 以下环境切换隐藏；`.responsive-table-card` 工具类 |
| D4. 暗色模式 | 确认所有组件在 `.dark` 下展示正常、图表配色暗色适配 | Zustand 三态切换（Light/Dark/System）；`localStorage` 持久化；监听系统主题变化；`--chart-1~5` 暗色变体 |
| D5. 加载骨架 | 为每个页面的数据区域定制 Skeleton 占位形状 | 7 个页面全部从"等宽方块"升级为与真实布局一致的骨架（表头+行/卡片+Footer/图表区域） |

---

## 9. 视觉设计规范

### 9.1 间距系统

基于 Tailwind 的 4px 基准：

| 场景 | 间距 | Tailwind |
|------|------|----------|
| 页面标题与内容间距 | 24px | `mb-6` |
| 卡片之间间距 | 24px | `gap-6` |
| 卡片内部 padding | 24px | `p-6` |
| 组件内部间距 | 16px | `gap-4` |
| 紧凑间距（列表项） | 12px | `gap-3` |
| 标签/图标间距 | 8px | `gap-2` |
| 最小间距 | 4px | `gap-1` |

### 9.2 字体层级

| 层级 | 大小 | 粗细 | 用途 |
|------|------|------|------|
| H1 页面标题 | `text-2xl` (24px) | `font-bold` (700) | 每个页面主标题 |
| H2 区块标题 | `text-lg` (18px) | `font-semibold` (600) | 卡片内 Section 标题 |
| H3 子标题 | `text-base` (16px) | `font-medium` (500) | 表格列头、表单标签 |
| Body 正文 | `text-sm` (14px) | `font-normal` (400) | 表格内容、描述文本 |
| Caption 辅助 | `text-xs` (12px) | `font-normal` (400) | 时间戳、辅助信息 |
| Overline | `text-xs` (12px) | `font-semibold` (600) | 状态标签、Badge 文字 |

### 9.3 阴影层级

```css
--shadow-sm:   0 1px 2px 0 rgb(0 0 0 / 0.05);    /* 卡片默认 */
--shadow-md:   0 4px 6px -1px rgb(0 0 0 / 0.1);  /* Dialog/Sheet 浮层 */
--shadow-lg:   0 10px 15px -3px rgb(0 0 0 / 0.1); /* DropdownMenu */
```

### 9.4 动画规范

| 场景 | 时长 | 缓动 | 实现 |
|------|------|------|------|
| Sidebar 展开/收缩 | 300ms | ease-in-out | `transition-all duration-300` |
| Dialog 进入/退出 | 200ms | ease-out | Radix 内置 |
| Hover 颜色变化 | 150ms | ease-in-out | `transition-colors` |
| Skeleton 闪烁 | 2s | ease-in-out 循环 | `animate-pulse` |
| Toast 滑入 | 300ms | ease-out | sonner 内置 |

### 9.5 图标规范

统一使用 `lucide-react`，尺寸统一：
- 导航图标：`h-5 w-5`
- 表格操作按钮：`h-4 w-4`
- 卡片内图标：`h-8 w-8`（带背景圆形容器）
- KPI 指标图标：`h-10 w-10`（带背景方形容器）

### 9.6 shadcn/ui 组件风格一致性

所有自定义组件需遵循 shadcn/ui 的 class-variance-authority (CVA) 模式：

```typescript
import { cva, type VariantProps } from "class-variance-authority";

const statusBadgeVariants = cva(
  "inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      status: {
        passed: "border-emerald-200 bg-emerald-50 text-emerald-700",
        failed: "border-red-200 bg-red-50 text-red-700",
        running: "border-blue-200 bg-blue-50 text-blue-700",
        pending: "border-amber-200 bg-amber-50 text-amber-700",
      },
    },
    defaultVariants: {
      status: "pending",
    },
  }
);
```

---

## 10. 前端技术特点

本项目前端在现代化 SPA 工程实践的基础上，融入了多项区分于常规 AI 生成代码的设计决策和技术特点。

### 10.1 架构特点

| 特点 | 说明 |
|------|------|
| **Hash 路由 + 前后端一体化部署** | `createHashRouter` 避免服务端 fallback 配置；Vite 构建产物直接输出到 `api/static/`，FastAPI 挂载静态文件即可一体化部署 |
| **双层状态管理** | Zustand 管理客户端全局状态（UI 状态、主题、侧边栏），TanStack React Query 管理服务端异步状态（缓存、自动刷新、乐观更新），清晰分离关注点 |
| **类型安全贯穿全栈** | TypeScript strict 模式开启，前端类型与后端 Pydantic Schema 对齐；Axios 响应拦截器自动解包 `SuccessResponse<T>`，返回类型完整的业务数据 |
| **mutation → invalidate 模式** | 所有写操作（创建/更新/删除）通过 React Query mutation，成功后自动 invalidate 相关 query，无需手动刷新数据 |
| **执行状态轮询** | `useExecutionStatus` 以 3s 间隔轮询 `GET /executions/{id}/status`，执行列表以 10s 间隔自动刷新，运行中行内嵌 Progress 进度条 |

### 10.2 UI/UX 特点

| 特点 | 说明 |
|------|------|
| **shadcn/ui 完整集成** | 34 个 shadcn/ui 组件全部通过 `components.json` 管理，底层基于 Radix UI 无样式原语，支持完整的 WAI-ARIA 无障碍访问 |
| **CSS 变量主题系统** | 全部颜色通过 HSL 变量定义（`--primary`、`--chart-1~5` 等），light/dark 双主题完整切换；图表配色不再硬编码，统一映射到 CSS 变量 |
| **三态主题切换** | 支持 Light → Dark → System 三种模式；System 模式监听 `prefers-color-scheme` 媒体查询实时响应；用户选择持久化到 `localStorage` |
| **拒绝 AI 通病设计** | 不使用紫色渐变、完全居中布局、千篇一律的三列卡片；采用非对称布局、差异化卡片尺寸、真实业务数据呈现 |
| **信息密度优化** | 表格从最初的 5 列扩展到 8-10 列；批量操作（勾选执行/删除）；⌘K 命令面板快速导航；Tab 筛选替代下拉筛选，减少点击步数 |
| **完整的空态/加载态/错误态** | 每个页面三级状态全覆盖：定制 Skeleton 骨架形状 → EmptyState 空态引导（含操作按钮）→ Toast 错误提示 |
| **微交互打磨** | 页面切换 fadeIn + translateY 动画；表格行 hover 背景过渡；卡片 hover lift 效果；Sidebar 展开/收缩 300ms 过渡；Toast 滑入通知 |

### 10.3 工程化特点

| 特点 | 说明 |
|------|------|
| **CVA 组件变体模式** | `StatusBadge` 和 `EmptyState` 等自定义组件遵循 shadcn/ui 的 class-variance-authority 模式，通过 variants 声明式管理样式变体 |
| **单文件类型定义** | `src/types/index.ts` 集中定义全部 TS 类型（~300 行），覆盖 6 个业务领域 + CRUD 请求/响应 + 通用分页包装 |
| **API 层统一封装** | `src/api/client.ts` 创建 axios 实例（baseURL `/api/v1`、30s 超时），响应拦截器自动解包后端 `SuccessResponse<T>` 包裹格式，错误统一提取 `detail` 字段 |
| **路径别名** | `@/` 映射到 `src/`，所有内部导入使用绝对路径，避免 `../../../` 深层相对路径 |
| **构建验证双保险** | `tsc -b && vite build` — 先 TypeScript 全量类型检查再 Vite 打包，确保零类型错误才能构建成功 |
| **组件数量规模化** | 34 个 shadcn/ui 组件 + 2 个自定义业务组件 + 3 个布局组件 = 39 个组件覆盖复杂的测试平台 UI |

### 10.4 对标设计原则

本项目的 UI 设计与 [design-workflow skill](https://www.codebuddy.ai/docs/) 的四条核心原则完全对齐：

1. **使用已有设计系统** ✅ — 全部颜色/圆角/阴影引用 CSS 变量，禁止硬编码；图表配色映射 `--chart-1~5`
2. **避免 AI 通病** ✅ — 不用紫色渐变；Dashboard 用非对称 5 列 KPI + 2×2 图表 + 底部全宽 Top N 列表的混合布局
3. **按组件逐层构建** ✅ — Phase A 先装组件 + 修类型 → Phase B 逐个页面重构 → Phase C 新页面 → Phase D 全站打磨
4. **真数据真内容** ✅ — 无 Lorem ipsum 占位；API 未就绪时展示 Skeleton 骨架而非假数据；空态使用真实业务语义

---

## 附录 A：文件变更清单

### 修改文件
```
frontend/src/types/index.ts          ← 类型修正
frontend/src/api/cases.ts            ← 新增 importFromUrl
frontend/src/api/executions.ts       ← 新增 getStatus
frontend/src/api/reports.ts          ← 拆分为 trends + topFailures
frontend/src/hooks/useReports.ts     ← 拆分 hooks
frontend/src/components/layout/Sidebar.tsx      ← 分组 + 新导航
frontend/src/components/layout/Header.tsx       ← 搜索 + 环境切换
frontend/src/components/layout/AppLayout.tsx    ← Toast + Breadcrumb
frontend/src/pages/CasesPage.tsx               ← 重构
frontend/src/pages/CaseEditPage.tsx             ← 重构
frontend/src/pages/ExecutionsPage.tsx           ← 重构
frontend/src/pages/ExecutionDetailPage.tsx      ← 重构
frontend/src/pages/DashboardPage.tsx            ← 重构
frontend/src/pages/EnvironmentsPage.tsx         ← 重构
frontend/src/router/index.tsx                   ← 新增路由
frontend/src/store/appStore.ts                  ← 新增 env/currentUser
```

### 新增文件
```
frontend/src/api/suites.ts
frontend/src/api/schedules.ts
frontend/src/hooks/useSuites.ts
frontend/src/hooks/useSchedules.ts
frontend/src/pages/SuitesPage.tsx
frontend/src/pages/CaseImportPage.tsx
frontend/src/pages/SchedulesPage.tsx
frontend/src/pages/CaseDetailPage.tsx
frontend/src/pages/ReportsPage.tsx
frontend/src/components/ui/tooltip.tsx          ← 新增 shadcn 组件
frontend/src/components/ui/sonner.tsx
frontend/src/components/ui/separator.tsx
frontend/src/components/ui/avatar.tsx
frontend/src/components/ui/accordion.tsx
frontend/src/components/ui/progress.tsx
frontend/src/components/ui/scroll-area.tsx
frontend/src/components/ui/command.tsx
frontend/src/components/ui/popover.tsx
frontend/src/components/ui/hover-card.tsx
frontend/src/components/ui/switch.tsx
frontend/src/components/ui/radio-group.tsx
frontend/src/components/ui/alert-dialog.tsx
frontend/src/components/ui/breadcrumb.tsx
frontend/src/components/ui/sheet.tsx
frontend/src/components/ui/calendar.tsx
frontend/src/components/ui/slider.tsx
frontend/src/components/ui/pagination.tsx
frontend/src/components/ui/status-badge.tsx     ← 自定义组件
frontend/src/components/ui/tag-input.tsx
frontend/src/components/ui/empty-state.tsx
```

---

## 附录 B：风险与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 后端 API 返回格式变化 | 前端类型再次不一致 | Phase A 优先修正类型，后续后端变更需同步更新前端类型 |
| shadcn/ui 组件升级 breaking change | 组件 API 不兼容 | 锁定 shadcn/ui 版本，升级前查阅 changelog |
| Charts (recharts) 复杂定制 | 开发周期延长 | 优先完成基础图表，高级图表第二阶段迭代 |
| OpenAPI 导入解析失败 | 导入页体验差 | 增加 URL 校验 + 格式检测 + 错误提示 |

---

> **下一步行动**：全部 4 个 Phase 已完成。后续进入维护迭代阶段，新增功能或页面在现有架构基础上扩展。
