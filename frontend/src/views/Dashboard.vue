<template>
  <div class="space-y-4">
    <!-- KPI 行（对应 .pen StatCard 实例） -->
    <div class="grid grid-cols-2 gap-4 xl:grid-cols-4">
      <div v-for="k in kpis" :key="k.label" class="rounded-xl border border-slate-200 bg-white p-[18px]">
        <div class="flex items-center justify-between">
          <span class="text-xs text-slate-500">{{ k.label }}</span>
          <component :is="k.icon" :size="15" :class="k.color" />
        </div>
        <p class="mt-2.5 text-[26px] font-bold" :class="k.color">{{ k.value }}</p>
        <p class="mt-1 text-[11px] text-slate-400">{{ k.sub }}</p>
      </div>
    </div>

    <div class="flex gap-4">
      <!-- 最新任务 -->
      <div class="flex-1 space-y-4">
        <div class="rounded-xl border border-slate-200 bg-white p-5">
          <div class="mb-4 flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <h3 class="text-sm font-semibold text-slate-900">最新任务</h3>
              <span
                class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium"
                :class="latestJob.statusClass"
              >
                <span class="h-1.5 w-1.5 rounded-full" :class="latestJob.dotClass" />
                {{ latestJob.statusLabel }}
              </span>
            </div>
            <span class="text-xs text-slate-500">{{ latestJob.timeText }}</span>
          </div>
          <div class="flex flex-wrap gap-x-9 gap-y-3">
            <div v-for="m in latestJob.meta" :key="m.k">
              <p class="text-[11px] text-slate-400">{{ m.k }}</p>
              <p class="text-[12.5px] font-medium text-slate-900">{{ m.v }}</p>
            </div>
          </div>
          <p v-if="latestJob.error" class="mt-3 rounded-md bg-red-50 px-3 py-2 font-mono text-[11px] text-red-600">
            {{ latestJob.error }}
          </p>
        </div>

        <!-- 数据速览 -->
        <div class="rounded-xl border border-slate-200 bg-white p-5">
          <div class="mb-3.5 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-900">今日热榜速览</h3>
            <router-link to="/data" class="text-xs text-blue-600 hover:underline">在数据浏览中查看 →</router-link>
          </div>
          <p v-if="!topNews.length" class="py-4 text-center text-xs text-slate-400">暂无数据，触发一次任务后展示</p>
          <div v-else class="space-y-2.5">
            <div v-for="n in topNews" :key="n.id" class="flex items-center gap-3">
              <span class="w-5 text-right text-sm font-bold" :class="n.rank <= 3 ? 'text-blue-600' : 'text-slate-300'">
                {{ n.rank }}
              </span>
              <span class="w-20 shrink-0 rounded bg-slate-50 px-2 py-0.5 text-center text-[11px] text-slate-500">
                {{ n.platform }}
              </span>
              <span class="min-w-0 flex-1 truncate text-[12.5px] text-slate-700">{{ n.title }}</span>
              <span class="shrink-0 text-[11px] text-slate-400">{{ n.crawl_count }} 次</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 调度卡 -->
      <div class="w-[360px] shrink-0 space-y-4">
        <div class="rounded-xl border border-slate-200 bg-white p-5">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-900">执行频率</h3>
            <span
              class="rounded-full px-2.5 py-0.5 text-[11px] font-medium"
              :class="schedule.enabled ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-400'"
            >
              {{ schedule.enabled ? '调度已启用' : '已停用' }}
            </span>
          </div>
          <div class="flex items-center gap-3">
            <Clock :size="16" class="text-blue-600" />
            <code class="rounded bg-slate-50 px-2 py-1 font-mono text-[13px] font-semibold text-slate-800">
              {{ schedule.cron || '—' }}
            </code>
          </div>
          <p class="mt-3 text-[11.5px] text-slate-500">
            下次触发：{{ nextRunText }}
          </p>
          <router-link
            to="/jobs"
            class="mt-4 flex items-center justify-center gap-2 rounded-lg bg-blue-600 py-2 text-[13px] font-medium text-white hover:bg-blue-700"
          >
            <Play :size="14" /> 立即运行
          </router-link>
        </div>

        <div class="rounded-xl border border-slate-200 bg-white p-5">
          <h3 class="mb-3 text-sm font-semibold text-slate-900">快速操作</h3>
          <div class="space-y-1">
            <router-link
              v-for="q in quicks"
              :key="q.label"
              :to="q.to"
              class="flex items-center gap-3 rounded-lg px-1.5 py-2 hover:bg-slate-50"
            >
              <component :is="q.icon" :size="16" class="text-slate-500" />
              <div class="min-w-0 flex-1">
                <p class="text-xs font-medium text-slate-800">{{ q.label }}</p>
                <p class="text-[11px] text-slate-400">{{ q.desc }}</p>
              </div>
              <ChevronRight :size="14" class="text-slate-300" />
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Clock, Play, ChevronRight, FileText, Table2, Activity } from 'lucide-vue-next'
import { api } from '../api/client'

const status = ref(null)
const jobs = ref([])
const news = ref([])
let timer = null

const kpis = computed(() => {
  const s = status.value
  const successRate = s && s.today_jobs ? Math.round((s.today_success / s.today_jobs) * 100) : 0
  return [
    { label: '今日运行', value: s ? `${s.today_jobs} 次` : '—', sub: `成功率 ${successRate}%`, icon: Activity, color: 'text-blue-600' },
    { label: '热榜条目', value: news.value.length ? String(newsTotal.value) : '—', sub: '今日数据库', icon: Table2, color: 'text-red-600' },
    { label: '调度状态', value: s && s.schedule.enabled ? '运行中' : '已停用', sub: s ? `${s.schedule.cron}` : '', icon: Clock, color: 'text-emerald-600' },
    { label: '数据用量', value: s ? `${(s.output_bytes / 1048576).toFixed(1)} MB` : '—', sub: 'output 目录', icon: FileText, color: 'text-amber-600' },
  ]
})

const newsTotal = ref(0)
const topNews = computed(() => news.value.slice(0, 5))

const schedule = computed(() => (status.value ? status.value.schedule : { enabled: false, cron: '', next_run: null }))

const nextRunText = computed(() => {
  const raw = schedule.value.next_run
  if (!raw) return '—'
  const d = new Date(raw)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

const latestJob = computed(() => {
  const job = jobs.value[0]
  if (!job) {
    return { statusLabel: '暂无任务', statusClass: 'bg-slate-100 text-slate-400', dotClass: 'bg-slate-300', timeText: '', meta: [], error: '' }
  }
  const map = {
    success: ['成功', 'bg-emerald-50 text-emerald-600', 'bg-emerald-500'],
    failed: ['失败', 'bg-red-50 text-red-600', 'bg-red-500'],
    running: ['运行中', 'bg-blue-50 text-blue-600', 'bg-blue-500'],
  }
  const [label, cls, dot] = map[job.status] || ['未知', 'bg-slate-100 text-slate-400', 'bg-slate-300']
  const dur = job.duration_ms ? `${(job.duration_ms / 1000).toFixed(0)}s` : '—'
  return {
    statusLabel: label,
    statusClass: cls,
    dotClass: dot,
    timeText: `#${job.id} · ${job.trigger} · 耗时 ${dur}`,
    meta: [
      { k: '触发方式', v: job.trigger === 'cron' ? 'cron 定时' : '手动' },
      { k: '配置版本', v: `#${job.config_version_id ?? '—'}` },
      { k: '退出码', v: String(job.exit_code ?? '—') },
    ],
    error: job.error_summary,
  }
})

const quicks = [
  { to: '/reports', label: '查看最新报告', desc: 'HTML 报告在线预览', icon: FileText },
  { to: '/jobs', label: '任务与日志', desc: '历史记录与实时日志', icon: Activity },
  { to: '/data', label: '数据浏览', desc: '热榜检索与过滤', icon: Table2 },
]

/** 拉取全部看板数据。 */
const refresh = async () => {
  try {
    const [s, j, n] = await Promise.all([
      api('/api/v1/system/status'),
      api('/api/v1/jobs?limit=1'),
      api('/api/v1/data/news?limit=5'),
    ])
    status.value = s
    jobs.value = j
    news.value = n.items
    newsTotal.value = n.total
  } catch {
    /* 轮询失败静默，下轮重试 */
  }
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 15000)
})
onUnmounted(() => clearInterval(timer))
</script>
