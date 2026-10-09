<template>
  <div class="flex h-full flex-col gap-4">
    <!-- 统计卡行（对应 .pen Screen Monitor MonStats） -->
    <div class="grid shrink-0 grid-cols-2 gap-3.5 xl:grid-cols-4">
      <div v-for="k in kpis" :key="k.label" class="rounded-xl border border-slate-200 bg-white p-4">
        <div class="flex items-center justify-between">
          <span class="text-xs text-slate-500">{{ k.label }}</span>
          <component :is="k.icon" :size="15" :class="k.color" />
        </div>
        <p class="mt-2 text-2xl font-bold" :class="k.color">{{ k.value }}</p>
        <p class="mt-0.5 text-[11px] text-slate-400">{{ k.sub }}</p>
      </div>
    </div>

    <!-- 操作条 -->
    <div class="flex shrink-0 flex-wrap items-center justify-between gap-3">
      <div class="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3.5 py-2">
        <Clock :size="14" class="text-slate-400" />
        <code class="font-mono text-xs text-slate-700">{{ schedule.cron || '—' }}</code>
        <span class="text-[11px] text-slate-400">下次 {{ nextRunText }}</span>
      </div>
      <div class="flex items-center gap-3">
        <span v-if="message" :class="isError ? 'text-red-500' : 'text-emerald-600'" class="text-xs">{{ message }}</span>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-[13px] font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          :disabled="triggering"
          @click="trigger"
        >
          <Play :size="14" /> {{ triggering ? '触发中…' : '手动触发' }}
        </button>
      </div>
    </div>

    <!-- 任务表 -->
    <div class="max-h-[236px] shrink-0 overflow-auto rounded-xl border border-slate-200 bg-white">
      <table class="w-full text-left">
        <thead class="sticky top-0 bg-slate-50 text-[11.5px] font-semibold text-slate-500">
          <tr>
            <th class="px-4 py-2.5">任务</th>
            <th class="px-4 py-2.5">状态</th>
            <th class="px-4 py-2.5">触发</th>
            <th class="px-4 py-2.5">开始时间</th>
            <th class="px-4 py-2.5">耗时</th>
            <th class="px-4 py-2.5">送达</th>
            <th class="px-4 py-2.5 text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="job in jobs"
            :key="job.id"
            class="cursor-pointer border-t border-slate-100 text-[12.5px] text-slate-600 transition-colors hover:bg-slate-50"
            :class="termJob?.id === job.id ? 'bg-blue-50/60' : ''"
            @click="focusJob(job)"
          >
            <td class="px-4 py-2 font-semibold text-slate-900">#{{ job.id }}</td>
            <td class="px-4 py-2">
              <span class="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium" :class="statusMeta(job.status).cls">
                <span class="h-1.5 w-1.5 rounded-full" :class="statusMeta(job.status).dot" />
                {{ statusMeta(job.status).label }}
              </span>
            </td>
            <td class="px-4 py-2">{{ job.trigger === 'cron' ? 'cron' : '手动' }}</td>
            <td class="px-4 py-2">{{ fmtTime(job.started_at) }}</td>
            <td class="px-4 py-2">{{ job.duration_ms ? `${(job.duration_ms / 1000).toFixed(0)}s` : '—' }}</td>
            <td class="px-4 py-2">
              <span v-if="job.channels_total" :class="job.channels_ok === job.channels_total ? 'text-emerald-600' : 'text-red-500'">
                {{ job.channels_ok }}/{{ job.channels_total }}
              </span>
              <span v-else class="text-slate-300">—</span>
            </td>
            <td class="px-4 py-2 text-right">
              <span class="inline-flex items-center gap-1.5 text-[11px] text-blue-600" @click.stop="focusJob(job)">
                <ScrollText :size="12" /> 日志
              </span>
            </td>
          </tr>
          <tr v-if="!jobs.length">
            <td colspan="7" class="px-4 py-8 text-center text-xs text-slate-400">暂无任务记录</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 底部：常驻日志终端 + 源健康（对应设计稿 BottomRow） -->
    <div class="flex min-h-0 flex-1 gap-4">
      <!-- 终端 -->
      <div class="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl bg-[#0D1424]">
        <div class="flex shrink-0 items-center gap-2 border-b border-slate-800 px-4 py-2.5">
          <span class="h-2.5 w-2.5 rounded-full bg-red-400" />
          <span class="h-2.5 w-2.5 rounded-full bg-amber-400" />
          <span class="h-2.5 w-2.5 rounded-full bg-green-400" />
          <span class="ml-2 text-[11.5px] text-slate-400">
            任务 {{ termJob ? `#${termJob.id}` : '—' }} · 实时日志
          </span>
          <span
            v-if="termJob?.status === 'running'"
            class="ml-auto inline-flex items-center gap-1.5 rounded-full bg-red-900/50 px-2 py-0.5 text-[9.5px] font-bold text-red-300"
          >
            <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-red-300" /> LIVE
          </span>
          <span v-else class="ml-auto font-mono text-[10px] text-slate-500">{{ wsAlive ? 'WS 已连接' : '轮询模式' }}</span>
        </div>
        <pre class="min-h-0 flex-1 overflow-y-auto p-3.5 font-mono text-[11px] leading-relaxed text-slate-300">{{ termText || '（点击上方任务行查看日志；触发新任务后自动跟踪）' }}</pre>
      </div>

      <!-- 源健康 -->
      <div class="flex w-[380px] shrink-0 flex-col rounded-xl border border-slate-200 bg-white p-4">
        <h3 class="mb-3 shrink-0 text-sm font-semibold text-slate-900">数据源健康 · 近 {{ health.days.length || 0 }} 天</h3>
        <div class="min-h-0 flex-1 space-y-1.5 overflow-y-auto">
          <p v-if="!health.platforms.length" class="py-6 text-center text-xs text-slate-400">暂无抓取记录</p>
          <template v-else>
            <div class="flex gap-1.5 pl-[70px]">
              <span v-for="d in health.days" :key="d" class="flex-1 text-center font-mono text-[9px] text-slate-400">{{ d.slice(5) }}</span>
            </div>
            <div v-for="p in health.platforms" :key="p.id" class="flex items-center gap-1.5">
              <span class="w-16 shrink-0 truncate text-right text-[11px] text-slate-600" :title="p.name">{{ p.name }}</span>
              <div
                v-for="(v, i) in p.values"
                :key="i"
                class="h-5 flex-1 rounded"
                :style="healthStyle(v)"
                :title="v === null ? '无数据' : `成功率 ${(v * 100).toFixed(0)}%`"
              />
            </div>
          </template>
        </div>
        <p v-if="weakSources.length" class="mt-2 shrink-0 rounded-md bg-amber-50 px-2.5 py-2 text-[10.5px] leading-relaxed text-amber-700">
          {{ weakSources }} 本周成功率偏低，建议启用代理或调整请求间隔。
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { Clock, Play, ScrollText, Activity, CheckCircle2, Timer, AlarmClock } from 'lucide-vue-next'
import { api } from '../api/client'
import { createStatusSocket } from '../api/ws'

const jobs = ref([])
const schedule = ref({ cron: '', enabled: false, next_run: null })
const triggering = ref(false)
const message = ref('')
const isError = ref(false)
const health = ref({ days: [], platforms: [] })
const termJob = ref(null)
const termText = ref('')
const wsAlive = ref(false)
let timer = null
let logTimer = null
let logOffset = 0
let socket = null

/* ---- 统计卡 ---- */
const todayStats = computed(() => {
  const today = jobs.value.filter((j) => j.started_at?.slice(0, 10) === new Date().toISOString().slice(0, 10))
  const success = today.filter((j) => j.status === 'success').length
  const durations = today.filter((j) => j.duration_ms).map((j) => j.duration_ms)
  const avg = durations.length ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length / 1000) : null
  return { total: today.length, success, avg }
})

const kpis = computed(() => {
  const s = todayStats.value
  const rate = s.total ? Math.round((s.success / s.total) * 100) : 0
  return [
    { label: '今日运行', value: `${s.total} 次`, sub: `成功率 ${rate}%`, icon: Activity, color: 'text-blue-600' },
    { label: '成功 / 失败', value: `${s.success} / ${s.total - s.success}`, sub: '今日任务', icon: CheckCircle2, color: s.total - s.success > 0 ? 'text-red-600' : 'text-emerald-600' },
    { label: '平均耗时', value: s.avg !== null ? `${s.avg}s` : '—', sub: '含 AI 分析', icon: Timer, color: 'text-slate-800' },
    { label: '下次运行', value: nextRunText.value, sub: schedule.value.enabled ? schedule.value.cron : '调度已停用', icon: AlarmClock, color: 'text-violet-600' },
  ]
})

const nextRunText = computed(() => {
  const raw = schedule.value.next_run
  if (!raw) return '—'
  const d = new Date(raw)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

/* ---- 源健康 ---- */
/** 健康块颜色。 @param {number|null} v */
const healthStyle = (v) => {
  if (v === null || v === undefined) return { backgroundColor: '#F1F5F9' }
  if (v >= 0.95) return { backgroundColor: '#10B981' }
  if (v >= 0.7) return { backgroundColor: '#F59E0B' }
  return { backgroundColor: '#EF4444' }
}
const weakSources = computed(() =>
  health.value.platforms
    .filter((p) => (p.values || []).some((v) => v !== null && v < 0.7))
    .map((p) => p.name)
    .join('、')
)

/* ---- 任务表 ---- */
/** 状态元数据。 @param {string} status */
const statusMeta = (status) =>
  ({
    success: { label: '成功', cls: 'bg-emerald-50 text-emerald-600', dot: 'bg-emerald-500' },
    failed: { label: '失败', cls: 'bg-red-50 text-red-600', dot: 'bg-red-500' },
    running: { label: '运行中', cls: 'bg-blue-50 text-blue-600', dot: 'bg-blue-500 animate-pulse' },
  })[status] || { label: status, cls: 'bg-slate-100 text-slate-400', dot: 'bg-slate-300' }

/** ISO 时间转本地时分秒。 @param {string} iso */
const fmtTime = (iso) => (iso ? new Date(iso).toLocaleTimeString('zh-CN', { hour12: false }) : '—')

/** 拉取任务列表/调度/健康。 */
const refresh = async () => {
  try {
    const [j, cfg, h] = await Promise.all([
      api('/api/v1/jobs?limit=30'),
      api('/api/v1/config/schedule').catch(() => schedule.value),
      api('/api/v1/data/platforms/health').catch(() => health.value),
    ])
    jobs.value = j
    schedule.value = cfg
    health.value = h
    if (!termJob.value && j.length) focusJob(j.find((x) => x.status === 'running') || j[0], false)
  } catch {
    /* 静默重试 */
  }
}

/** 手动触发。 */
const trigger = async () => {
  triggering.value = true
  isError.value = false
  message.value = ''
  try {
    const job = await api('/api/v1/jobs/trigger', { method: 'POST', body: '{}' })
    message.value = `任务 #${job.id} 已触发`
    await refresh()
    focusJob(jobs.value.find((j) => j.id === job.id) || { id: job.id, status: 'running' }, true)
  } catch (e) {
    isError.value = true
    message.value = e.message
  } finally {
    triggering.value = false
  }
}

/* ---- 常驻终端 ---- */
/** 切换终端跟踪目标。 @param {object} job @param {boolean} reset */
const focusJob = async (job, reset = true) => {
  termJob.value = job
  if (reset) termText.value = ''
  logOffset = 0
  clearInterval(logTimer)
  try {
    const data = await api(`/api/v1/jobs/${job.id}/logs?offset=0`)
    termText.value = data.text
    logOffset = data.next_offset
  } catch {
    /* 历史读取失败静默 */
  }
  scrollToBottom()
  if (!wsAlive.value) logTimer = setInterval(pollLog, 2000)
}

/** 轮询兜底增量。 */
const pollLog = async () => {
  if (!termJob.value) return
  try {
    const data = await api(`/api/v1/jobs/${termJob.value.id}/logs?offset=${logOffset}`)
    termText.value += data.text
    logOffset = data.next_offset
    scrollToBottom()
  } catch {
    /* 静默 */
  }
}

/** 终端滚底。 */
const scrollToBottom = () => {
  requestAnimationFrame(() => {
    const box = document.querySelector('pre')
    if (box) box.scrollTop = box.scrollHeight
  })
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 30000)
  socket = createStatusSocket((event) => {
    if (socket) wsAlive.value = socket.alive()
    if (event.type === 'log') {
      if (termJob.value && termJob.value.id === event.job_id) {
        termText.value += event.text
        scrollToBottom()
      }
    } else if (event.type === 'status') {
      refresh()
      if (termJob.value && termJob.value.id === event.job_id) {
        termJob.value.status = event.status
        if (event.status !== 'running' && !wsAlive.value) {
          clearInterval(logTimer)
          logTimer = setInterval(pollLog, 2000)
        }
      }
    }
  })
})
onUnmounted(() => {
  clearInterval(timer)
  clearInterval(logTimer)
  if (socket) socket.close()
})
</script>
