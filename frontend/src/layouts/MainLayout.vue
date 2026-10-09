<template>
  <div class="flex h-screen bg-slate-100">
    <!-- 侧边栏（对应 .pen Component Sidebar） -->
    <aside class="flex w-60 shrink-0 flex-col bg-sidebar px-3.5 py-5">
      <div class="mb-4 flex items-center gap-2.5 px-2 pb-3">
        <div class="flex h-[30px] w-[30px] items-center justify-center rounded-lg bg-blue-600">
          <Radar :size="16" class="text-white" />
        </div>
        <div>
          <p class="text-sm font-semibold text-slate-100">TrendRadar</p>
          <p class="text-[10px] text-slate-400">管理平台 v1.0</p>
        </div>
      </div>

      <nav v-for="group in navGroups" :key="group.label" class="mb-1.5">
        <p class="px-2.5 py-1 text-[10px] tracking-widest text-slate-500">{{ group.label }}</p>
        <router-link
          v-for="item in group.items"
          :key="item.to"
          :to="item.to"
          class="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] text-slate-400 transition-colors hover:text-slate-200"
          :class="{ 'bg-sidebar-active !text-slate-100': isActive(item.to) }"
        >
          <component :is="item.icon" :size="16" />
          {{ item.label }}
        </router-link>
      </nav>

      <div class="mt-auto flex items-center gap-2.5 px-2 pt-3">
        <div class="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-blue-700 text-xs font-semibold text-white">
          {{ auth.username.charAt(0).toUpperCase() }}
        </div>
        <div class="flex-1">
          <p class="text-xs font-medium text-slate-100">{{ auth.username }}</p>
          <p class="text-[10px] text-slate-400">管理员</p>
        </div>
        <button title="退出登录" @click="logout" class="text-slate-500 hover:text-slate-200">
          <LogOut :size="15" />
        </button>
      </div>
    </aside>

    <!-- 主区 -->
    <div class="flex min-w-0 flex-1 flex-col">
      <header class="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-7">
        <div class="flex items-center gap-2.5">
          <h1 class="text-base font-semibold text-slate-900">{{ pageTitle }}</h1>
          <span class="text-xs text-slate-400">{{ pageCrumb }}</span>
        </div>
        <slot name="topbar" />
      </header>
      <main class="min-h-0 flex-1 overflow-y-auto p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Radar, LayoutDashboard, Table2, Settings2, FileText, Activity, LogOut, Wrench } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navGroups = [
  { label: '概览', items: [{ to: '/dashboard', label: '仪表盘', icon: LayoutDashboard }] },
  { label: '数据', items: [{ to: '/data', label: '数据浏览', icon: Table2 }] },
  {
    label: '管理',
    items: [
      { to: '/config', label: '配置管理', icon: Settings2 },
      { to: '/jobs', label: '运行监控', icon: Activity },
      { to: '/reports', label: '报告中心', icon: FileText },
    ],
  },
  {
    label: '系统',
    items: [{ to: '/settings', label: '系统设置', icon: Wrench }],
  },
]

const pageTitle = computed(() =>
  ({ dashboard: '仪表盘', config: '配置管理', data: '数据浏览', jobs: '运行监控', reports: '报告中心', settings: '系统设置' }[route.path.split('/')[1]] || 'TrendRadar')
)
const pageCrumb = computed(() =>
  ({ dashboard: '/ 概览', config: '/ 数据源 · 调度 · 筛选 · AI · 版本', data: '/ 热榜数据', jobs: '/ 任务与日志', reports: '/ 历史报告', settings: '/ 账户 · 存储 · 版本 · 审计' }[route.path.split('/')[1]] || '')
)

/** 判断导航激活态。 @param {string} to */
const isActive = (to) => route.path.startsWith(to)

/** 退出登录并回登录页。 */
const logout = () => {
  auth.logout()
  router.push('/login')
}
</script>
