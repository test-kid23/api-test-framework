<script setup lang="ts">
import { ref, h, onMounted } from 'vue'
import { MessagePlugin, DialogPlugin } from 'tdesign-vue-next'
import { MailIcon, HeartIcon, SettingIcon, BrowseIcon } from 'tdesign-icons-vue-next'

// Button state
const loadingBtn = ref(false)

// Form state
const formData = ref({
  name: '张三',
  email: '',
  password: 'password123',
  city: 'beijing',
  date: '2026-06-08',
  desc: '这是一个基于 Vue 3 + TDesign 的现代化前端项目，采用企业级设计系统，组件开箱即用，全面覆盖中后台业务场景。',
})
const techChecked = ref(['vue', 'react'])
const radioChoice = ref('vue')
const emailNotify = ref(true)
const smsNotify = ref(false)

// Dialog
const dialogVisible = ref(false)

// Table data
const tableColumns = [
  { colKey: 'id', title: 'ID', width: 60 },
  { colKey: 'name', title: '接口名称' },
  { colKey: 'method', title: '方法', width: 80 },
  { colKey: 'status', title: '状态', width: 100 },
  { colKey: 'duration', title: '耗时', width: 100 },
]
const tableData = ref([
  { id: 1, name: '用户登录接口', method: 'POST', status: '通过', duration: '235ms' },
  { id: 2, name: '订单列表查询', method: 'GET', status: '通过', duration: '412ms' },
  { id: 3, name: '商品详情获取', method: 'GET', status: '失败', duration: '89ms' },
  { id: 4, name: '数据导出任务', method: 'POST', status: '运行中', duration: '1.2s' },
])

// Tabs
const activeTab = ref('overview')

// Sidebar
const activeSection = ref('buttons')
const sections = [
  { id: 'buttons', label: '按钮 Button' },
  { id: 'forms', label: '表单 Form' },
  { id: 'data', label: '数据展示 Data' },
  { id: 'navigation', label: '导航 Navigation' },
  { id: 'feedback', label: '反馈 Feedback' },
]

const scrollTo = (id: string) => {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// Intersection Observer for sidebar
onMounted(() => {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) activeSection.value = entry.target.id
      })
    },
    { rootMargin: '-20% 0px -70% 0px' }
  )
  sections.forEach(({ id }) => {
    const el = document.getElementById(id)
    if (el) observer.observe(el)
  })
})

// Toast handlers
const showSuccess = () => MessagePlugin.success('操作成功！测试用例已保存。')
const showInfo = () => MessagePlugin.info('定时任务将在 5 分钟后开始执行。')
const showError = () => MessagePlugin.error('接口调用失败：连接超时，请重试。')
const showWarning = () => MessagePlugin.warning('检测到版本更新，建议重新加载页面。')

const openDeleteDialog = () => {
  const dialog = DialogPlugin.confirm({
    header: '确认删除测试用例？',
    body: '该操作将永久删除"用户登录接口验证"测试用例及其关联的所有执行历史记录，此操作不可恢复。',
    confirmBtn: '确认删除',
    cancelBtn: '取消',
    theme: 'danger',
    onConfirm: () => {
      MessagePlugin.success('测试用例已成功删除')
      dialog.hide()
    },
  })
}

const techOptions = [
  { value: 'react', label: 'React' },
  { value: 'vue', label: 'Vue' },
  { value: 'angular', label: 'Angular / Svelte' },
]
const cityOptions = [
  { value: 'beijing', label: '北京' },
  { value: 'shanghai', label: '上海' },
  { value: 'shenzhen', label: '深圳' },
  { value: 'hangzhou', label: '杭州' },
]
const pagination = ref({ current: 1, pageSize: 20, total: 342 })
</script>

<template>
  <div class="app-container">
    <!-- Top Navbar -->
    <header class="top-navbar">
      <div class="nav-left">
        <t-icon name="logo-github" size="20px" style="color: #60a5fa" />
        <span class="nav-title">Vue 3 + TDesign</span>
        <span class="nav-subtitle">组件展示 Demo</span>
      </div>
      <div class="nav-right">
        <t-tag theme="primary" variant="light-outline" size="small">Vue 3</t-tag>
        <t-tag theme="default" variant="light-outline" size="small">TDesign</t-tag>
        <t-tag theme="success" variant="light-outline" size="small">TypeScript</t-tag>
      </div>
    </header>

    <!-- Sidebar -->
    <aside class="side-nav">
      <div class="side-nav-header">组件导航</div>
      <nav>
        <button
          v-for="s in sections"
          :key="s.id"
          :class="['side-nav-item', { active: activeSection === s.id }]"
          @click="scrollTo(s.id)"
        >
          {{ s.label }}
        </button>
      </nav>
    </aside>

    <!-- Main Content -->
    <main class="main-content">
      <div class="content-wrapper">
        <div class="page-header">
          <h1>Vue 3 + TDesign 组件展示</h1>
          <p>腾讯开源企业级设计体系 · 开箱即用 · 覆盖中后台全场景</p>
        </div>

        <!-- Buttons Section -->
        <section id="buttons" class="demo-card">
          <div class="card-header">
            <h2>按钮 Button</h2>
            <p>五种主题 × 三种尺寸，支持图标、加载和禁用状态</p>
          </div>
          <div class="card-body">
            <h3 class="section-subtitle">主题 × 尺寸矩阵</h3>
            <table class="btn-matrix">
              <thead>
                <tr>
                  <th></th>
                  <th>Small</th>
                  <th>Medium</th>
                  <th>Large</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="theme in ['default', 'primary', 'success', 'warning', 'danger']" :key="theme">
                  <td class="matrix-label">{{ theme === 'default' ? 'Default' : theme.charAt(0).toUpperCase() + theme.slice(1) }}</td>
                  <td><t-button :theme="theme as any" size="small">按钮</t-button></td>
                  <td><t-button :theme="theme as any" size="medium">按钮</t-button></td>
                  <td><t-button :theme="theme as any" size="large">按钮</t-button></td>
                </tr>
              </tbody>
            </table>

            <div class="divider"></div>

            <h3 class="section-subtitle">带图标按钮</h3>
            <t-space>
              <t-button theme="primary"><mail-icon /> 邮箱</t-button>
              <t-button theme="default"><setting-icon /> 设置</t-button>
              <t-button variant="outline"><heart-icon /> 收藏</t-button>
              <t-button variant="text"><heart-icon /> 喜欢</t-button>
            </t-space>

            <div class="divider"></div>

            <h3 class="section-subtitle">状态展示</h3>
            <t-space>
              <t-button theme="primary" :loading="true">加载中</t-button>
              <t-button :disabled="true">已禁用</t-button>
              <t-button variant="outline" :disabled="true">禁用边框</t-button>
              <t-button theme="default" :disabled="true">禁用默认</t-button>
            </t-space>
          </div>
        </section>

        <!-- Forms Section -->
        <section id="forms" class="demo-card">
          <div class="card-header">
            <h2>表单 Form</h2>
            <p>常用表单控件一览，均可交互</p>
          </div>
          <div class="card-body">
            <div class="form-grid">
              <div class="form-item">
                <label>姓名</label>
                <t-input v-model="formData.name" placeholder="请输入姓名" />
              </div>
              <div class="form-item">
                <label>邮箱</label>
                <t-input v-model="formData.email" type="email" placeholder="name@example.com" />
              </div>
              <div class="form-item">
                <label>密码</label>
                <t-input v-model="formData.password" type="password" placeholder="请输入密码" />
              </div>
              <div class="form-item">
                <label>城市</label>
                <t-select v-model="formData.city" :options="cityOptions" placeholder="请选择城市" />
              </div>
              <div class="form-item">
                <label>技术偏好（多选）</label>
                <t-checkbox-group v-model="techChecked" :options="techOptions" />
              </div>
              <div class="form-item">
                <label>主要使用框架</label>
                <t-radio-group v-model="radioChoice">
                  <t-radio value="vue">Vue</t-radio>
                  <t-radio value="react">React</t-radio>
                  <t-radio value="other">其他</t-radio>
                </t-radio-group>
              </div>
              <div class="form-item">
                <label>通知设置</label>
                <div class="switch-group">
                  <t-switch v-model="emailNotify" />
                  <span>邮件通知 {{ emailNotify ? '（已开启）' : '（已关闭）' }}</span>
                </div>
                <div class="switch-group">
                  <t-switch v-model="smsNotify" />
                  <span>短信通知 {{ smsNotify ? '（已开启）' : '（已关闭）' }}</span>
                </div>
              </div>
              <div class="form-item">
                <label>日期选择</label>
                <t-date-picker v-model="formData.date" />
              </div>
            </div>
            <div class="form-item" style="margin-top: 16px">
              <label>项目描述</label>
              <t-textarea v-model="formData.desc" placeholder="请输入项目描述..." :autosize="{ minRows: 3, maxRows: 5 }" />
            </div>
          </div>
        </section>

        <!-- Data Section -->
        <section id="data" class="demo-card">
          <div class="card-header">
            <h2>数据展示 Data Display</h2>
            <p>表格、卡片、标签组件一览</p>
          </div>
          <div class="card-body">
            <h3 class="section-subtitle">数据表格</h3>
            <t-table
              :data="tableData"
              :columns="tableColumns"
              :bordered="true"
              :stripe="true"
              row-key="id"
              size="medium"
            >
              <template #status="{ row }">
                <t-tag
                  :theme="row.status === '通过' ? 'success' : row.status === '失败' ? 'danger' : 'warning'"
                  variant="light"
                  size="small"
                >
                  {{ row.status }}
                </t-tag>
              </template>
              <template #method="{ row }">
                <t-tag theme="default" variant="outline" size="small">{{ row.method }}</t-tag>
              </template>
            </t-table>

            <div class="divider"></div>

            <h3 class="section-subtitle">卡片组件</h3>
            <t-row :gutter="16">
              <t-col :span="6">
                <t-card title="API 测试框架" description="企业级自动化测试解决方案" :bordered="true" hover-shadow>
                  <p class="card-text">支持 HTTP、gRPC、WebSocket 多协议测试，内置断言引擎与报告生成，具备分布式执行能力。</p>
                  <template #actions>
                    <t-button variant="text" theme="primary"><browse-icon /> 查看详情</t-button>
                  </template>
                </t-card>
              </t-col>
              <t-col :span="6">
                <t-card title="多协议支持" description="覆盖主流 API 协议" :bordered="true" hover-shadow>
                  <t-space>
                    <t-tag theme="primary" variant="light">HTTP/HTTPS</t-tag>
                    <t-tag theme="success" variant="light">gRPC</t-tag>
                    <t-tag theme="warning" variant="light">WebSocket</t-tag>
                    <t-tag theme="default" variant="light">GraphQL</t-tag>
                    <t-tag theme="danger" variant="light">TCP</t-tag>
                  </t-space>
                  <template #actions>
                    <span style="font-size: 12px; color: var(--td-text-color-placeholder)">已集成 5 种协议支持</span>
                  </template>
                </t-card>
              </t-col>
            </t-row>

            <div class="divider"></div>

            <h3 class="section-subtitle">标签 / Tag</h3>
            <t-space>
              <t-tag theme="primary">Primary</t-tag>
              <t-tag theme="success">Success</t-tag>
              <t-tag theme="warning">Warning</t-tag>
              <t-tag theme="danger">Danger</t-tag>
              <t-tag theme="default">Default</t-tag>
              <t-tag variant="outline">Outline</t-tag>
              <t-tag variant="light">Light</t-tag>
              <t-tag :closable="true" @close="() => {}">可关闭</t-tag>
            </t-space>
          </div>
        </section>

        <!-- Navigation Section -->
        <section id="navigation" class="demo-card">
          <div class="card-header">
            <h2>导航 Navigation</h2>
            <p>标签页、面包屑、分页组件</p>
          </div>
          <div class="card-body">
            <h3 class="section-subtitle">标签页 Tabs</h3>
            <t-tabs v-model="activeTab">
              <t-tab-panel value="overview" label="概览">
                <p class="tab-content">今日执行 128 条用例，通过率 97.6%，平均响应时间 234ms。</p>
              </t-tab-panel>
              <t-tab-panel value="cases" label="测试用例">
                <p class="tab-content">共 342 条测试用例，覆盖 45 个 API 接口。可在此管理用例增删改查。</p>
              </t-tab-panel>
              <t-tab-panel value="reports" label="测试报告">
                <p class="tab-content">最近 7 天生成了 24 份测试报告，支持 HTML / Allure / JSON 格式导出。</p>
              </t-tab-panel>
              <t-tab-panel value="settings" label="设置">
                <p class="tab-content">配置全局超时、重试策略、并发数等执行参数。当前环境：Staging。</p>
              </t-tab-panel>
            </t-tabs>

            <div class="divider"></div>

            <h3 class="section-subtitle">面包屑 Breadcrumb</h3>
            <t-breadcrumb>
              <t-breadcrumb-item>首页</t-breadcrumb-item>
              <t-breadcrumb-item>项目中心</t-breadcrumb-item>
              <t-breadcrumb-item>API 测试框架</t-breadcrumb-item>
              <t-breadcrumb-item>用例详情</t-breadcrumb-item>
            </t-breadcrumb>

            <div class="divider"></div>

            <h3 class="section-subtitle">分页 Pagination</h3>
            <t-pagination
              v-model="pagination.current"
              :total="pagination.total"
              :page-size="pagination.pageSize"
              show-jumper
              show-page-size
            />
          </div>
        </section>

        <!-- Feedback Section -->
        <section id="feedback" class="demo-card">
          <div class="card-header">
            <h2>反馈 Feedback</h2>
            <p>对话框、消息提示、骨架屏组件</p>
          </div>
          <div class="card-body">
            <h3 class="section-subtitle">对话框 Dialog</h3>
            <t-space>
              <t-button theme="primary" @click="openDeleteDialog">打开对话框</t-button>
              <t-button theme="warning" @click="dialogVisible = true">
                <browse-icon /> 查看详情
              </t-button>
            </t-space>
            <t-dialog
              v-model:visible="dialogVisible"
              header="测试执行报告"
              :confirm-btn="null"
              cancel-btn="关闭"
            >
              <p>本次测试共执行 342 条用例，通过 334 条，失败 8 条，通过率 97.6%。</p>
              <p style="margin-top: 8px">平均响应时间 234ms，最大响应时间 1.2s，整体表现良好。</p>
            </t-dialog>

            <div class="divider"></div>

            <h3 class="section-subtitle">消息提示 Toast</h3>
            <t-space>
              <t-button theme="success" @click="showSuccess">成功消息</t-button>
              <t-button theme="primary" @click="showInfo">普通消息</t-button>
              <t-button theme="danger" @click="showError">错误消息</t-button>
              <t-button variant="outline" @click="showWarning">警告消息</t-button>
            </t-space>

            <div class="divider"></div>

            <h3 class="section-subtitle">骨架屏 Skeleton</h3>
            <div class="skeleton-demo">
              <t-skeleton theme="avatar" />
              <t-skeleton :row-col="[{ width: '200px' }, { width: '150px' }]" style="margin-top: 12px" />
              <t-skeleton :row-col="[{ height: '120px' }]" style="margin-top: 12px" />
              <t-skeleton :row-col="[1, 1, { width: '60%' }]" style="margin-top: 12px" />
              <t-skeleton :row-col="[{ width: '80px', height: '36px' }, { width: '80px', height: '36px' }]" style="margin-top: 12px" />
            </div>
          </div>
        </section>
      </div>

      <!-- Footer -->
      <footer class="page-footer">
        <p>Vue 3 + TDesign 组件展示 Demo · 仅供技术选型参考 · 2026</p>
        <p class="footer-sub">Built with Vue 3 · TDesign Vue Next · TypeScript</p>
      </footer>
    </main>
  </div>
</template>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', 'PingFang SC', -apple-system, sans-serif;
  background: #F1F5F9;
  color: #0F172A;
}

.app-container {
  min-height: 100vh;
}

/* Top Navbar */
.top-navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
  height: 56px;
  background: #0F172A;
  border-bottom: 1px solid rgba(51, 65, 85, 0.5);
  display: flex;
  align-items: center;
  padding: 0 24px;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-title {
  color: #FFFFFF;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: -0.3px;
}

.nav-subtitle {
  color: #94A3B8;
  font-size: 14px;
  margin-left: 4px;
}

.nav-right {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

/* Sidebar */
.side-nav {
  position: fixed;
  top: 56px;
  left: 0;
  bottom: 0;
  width: 180px;
  background: #F8FAFC;
  border-right: 1px solid #E2E8F0;
  z-index: 40;
  overflow-y: auto;
  padding: 16px;
}

.side-nav-header {
  font-size: 11px;
  font-weight: 600;
  color: #94A3B8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 16px;
}

.side-nav-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 10px 12px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #64748B;
  background: none;
  border: none;
  cursor: pointer;
  border-left: 2px solid transparent;
  transition: all 0.2s;
  margin-bottom: 4px;
}

.side-nav-item:hover {
  background: #F1F5F9;
  color: #334155;
}

.side-nav-item.active {
  background: #EFF6FF;
  color: #1D4ED8;
  border-left-color: #2563EB;
}

/* Main Content */
.main-content {
  margin-left: 180px;
  padding-top: 56px;
}

.content-wrapper {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 32px 0;
}

.page-header {
  margin-bottom: 32px;
}

.page-header h1 {
  font-size: 28px;
  font-weight: 700;
  color: #0F172A;
}

.page-header p {
  color: #64748B;
  margin-top: 8px;
  font-size: 14px;
}

/* Demo Card */
.demo-card {
  background: #FFFFFF;
  border-radius: 12px;
  border: 1px solid #E2E8F0;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  margin-bottom: 40px;
  overflow: hidden;
}

.card-header {
  padding: 16px 24px;
  border-bottom: 1px solid #F1F5F9;
  background: linear-gradient(to right, #F8FAFC, #FFFFFF);
}

.card-header h2 {
  font-size: 20px;
  font-weight: 700;
  color: #0F172A;
}

.card-header p {
  font-size: 14px;
  color: #64748B;
  margin-top: 4px;
}

.card-body {
  padding: 24px;
}

.section-subtitle {
  font-size: 14px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 12px;
}

.divider {
  height: 1px;
  background: #E2E8F0;
  margin: 24px 0;
}

/* Button Matrix */
.btn-matrix {
  width: 100%;
  border-collapse: collapse;
}

.btn-matrix th {
  text-align: center;
  font-size: 12px;
  color: #94A3B8;
  font-weight: 500;
  padding: 8px;
}

.btn-matrix td {
  padding: 8px;
  text-align: center;
}

.matrix-label {
  text-align: left !important;
  font-size: 12px;
  font-weight: 500;
  color: #64748B;
}

/* Form Grid */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-item label {
  font-size: 14px;
  font-weight: 500;
  color: #0F172A;
}

.switch-group {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #334155;
}

/* Card text */
.card-text {
  font-size: 14px;
  color: #475569;
  line-height: 1.6;
}

/* Tab content */
.tab-content {
  padding: 16px;
  border: 1px solid #E2E8F0;
  border-radius: 6px;
  margin-top: 8px;
  font-size: 14px;
  color: #475569;
}

/* Skeleton demo */
.skeleton-demo {
  max-width: 400px;
  padding: 16px;
  border: 1px solid #E2E8F0;
  border-radius: 8px;
}

/* Footer */
.page-footer {
  border-top: 1px solid #E2E8F0;
  background: #F8FAFC;
  padding: 32px;
  text-align: center;
}

.page-footer p {
  font-size: 14px;
  color: #64748B;
}

.footer-sub {
  font-size: 12px !important;
  color: #94A3B8 !important;
  margin-top: 4px;
}
</style>
