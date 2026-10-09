<template>
  <div class="flex h-screen bg-white">
    <!-- 左侧品牌区（对应 .pen Screen Login） -->
    <div
      class="hidden w-[57%] flex-col justify-between p-16 lg:flex"
      :style="{ background: 'linear-gradient(200deg, #0B1220 0%, #12275C 60%, #1D4ED8 100%)' }"
    >
      <div class="flex items-center gap-3">
        <div class="flex h-9 w-9 items-center justify-center rounded-[10px] bg-blue-600">
          <Radar :size="20" class="text-white" />
        </div>
        <span class="text-lg font-bold text-white">TrendRadar</span>
      </div>
      <div class="max-w-[560px]">
        <h1 class="text-[44px] font-bold leading-tight text-white">热点尽在掌握</h1>
        <p class="mt-5 text-[15px] leading-relaxed text-[#B6C5E8]">
          聚合 11 个热榜平台与 RSS 订阅源，AI 筛选、分析与多渠道推送，一个界面管理一切。
        </p>
        <div class="mt-7 space-y-3.5">
          <div v-for="f in features" :key="f.title" class="flex items-center gap-3">
            <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-white/10">
              <component :is="f.icon" :size="15" class="text-[#93B4F8]" />
            </div>
            <div>
              <p class="text-[13px] font-semibold text-white">{{ f.title }}</p>
              <p class="text-xs text-[#8FA3C8]">{{ f.desc }}</p>
            </div>
          </div>
        </div>
      </div>
      <p class="text-[11px] text-[#5E719A]">v6.5.0 引擎 · MCP v4.0.0 · GPL-3.0</p>
    </div>

    <!-- 右侧表单 -->
    <div class="flex flex-1 items-center justify-center">
      <form class="w-[340px] space-y-5" @submit.prevent="submit">
        <div class="space-y-2">
          <h2 class="text-2xl font-bold text-slate-900">欢迎回来</h2>
          <p class="text-[13px] text-slate-500">登录 TrendRadar 管理平台</p>
        </div>
        <label class="block space-y-1.5">
          <span class="text-xs font-medium text-slate-600">用户名</span>
          <input
            v-model="username"
            class="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-[13px] outline-none focus:border-blue-500"
            placeholder="admin"
            autocomplete="username"
          />
        </label>
        <label class="block space-y-1.5">
          <span class="text-xs font-medium text-slate-600">密码</span>
          <input
            v-model="password"
            type="password"
            class="w-full rounded-lg border border-slate-200 px-3.5 py-2.5 text-[13px] outline-none focus:border-blue-500"
            placeholder="••••••••"
            autocomplete="current-password"
          />
        </label>
        <p v-if="error" class="rounded-md bg-red-50 px-3 py-2 text-xs text-red-600">{{ error }}</p>
        <button
          type="submit"
          :disabled="loading"
          class="w-full rounded-lg bg-blue-600 py-2.5 text-[13px] font-semibold text-white transition hover:bg-blue-700 disabled:opacity-60"
        >
          {{ loading ? '登录中…' : '登 录' }}
        </button>
        <p class="text-[11px] leading-relaxed text-slate-400">
          单管理员模式 · 初始密码由 WEB_ADMIN_PASSWORD 环境变量设置（默认 trendradar）
        </p>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Radar, Settings2, Activity, Table2 } from 'lucide-vue-next'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const username = ref('admin')
const password = ref('')
const error = ref('')
const loading = ref(false)

const features = [
  { icon: Settings2, title: '可视化配置', desc: '数据源、调度、AI 与通知全部界面化' },
  { icon: Activity, title: '运行可观测', desc: '任务历史、日志与源健康度实时掌握' },
  { icon: Table2, title: '数据资产化', desc: '历史热榜与趋势分析随时检索' },
]

/** 提交登录。 */
const submit = async () => {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push('/dashboard')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>
