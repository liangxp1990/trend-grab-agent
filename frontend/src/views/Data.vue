<template>
  <div class="flex h-full flex-col gap-4">
    <!-- 模式切换 -->
    <div class="flex shrink-0 items-center justify-between">
      <div class="flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
        <button
          v-for="t in modes"
          :key="t.key"
          class="rounded-md px-3.5 py-1.5 text-xs font-medium transition"
          :class="mode === t.key ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:text-slate-700'"
          @click="mode = t.key"
        >
          {{ t.label }}
        </button>
      </div>
      <button
        v-if="mode === 'trends'"
        class="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-600 hover:bg-slate-50"
        @click="loadTrends(true)"
      >
        <RefreshCw :size="13" /> 刷新
      </button>
    </div>

    <!-- ============ 热榜查询 ============ -->
    <template v-if="mode === 'news'">
      <div class="flex flex-wrap items-center gap-3">
        <select v-model="date" class="rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs text-slate-600 outline-none focus:border-blue-500">
          <option v-for="d in dates" :key="d" :value="d">{{ d }}</option>
        </select>
        <input
          v-model.trim="keyword"
          placeholder="搜索标题关键词…"
          class="min-w-[220px] flex-1 rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-xs outline-none focus:border-blue-500"
          @keyup.enter="search"
        />
        <button class="rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-700" @click="search">查询</button>
      </div>

      <div class="min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-200 bg-white">
        <div class="h-full overflow-y-auto">
          <table class="w-full text-left">
            <thead class="sticky top-0 z-10 bg-slate-50 text-[11.5px] font-semibold text-slate-500">
              <tr>
                <th class="w-14 px-4 py-2.5">排名</th>
                <th class="px-4 py-2.5">标题</th>
                <th class="w-24 px-4 py-2.5">平台</th>
                <th class="w-20 px-4 py-2.5">出现</th>
                <th class="w-40 px-4 py-2.5">首次 / 最后</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="n in items" :key="n.id + n.platform" class="border-t border-slate-100 text-[12.5px]">
                <td class="px-4 py-2.5 text-[15px] font-bold" :class="n.rank <= 3 ? 'text-blue-600' : 'text-slate-300'">{{ n.rank }}</td>
                <td class="max-w-0 px-4 py-2.5">
                  <a :href="n.url" target="_blank" class="block truncate text-slate-800 hover:text-blue-600 hover:underline" :title="n.title">{{ n.title }}</a>
                </td>
                <td class="px-4 py-2.5"><span class="rounded bg-slate-50 px-2 py-0.5 text-[11px] text-slate-500">{{ n.platform }}</span></td>
                <td class="px-4 py-2.5 text-xs text-slate-500">{{ n.crawl_count }} 次</td>
                <td class="px-4 py-2.5 text-[11px] text-slate-400">{{ fmt(n.first_crawl_time) }} / {{ fmt(n.last_crawl_time) }}</td>
              </tr>
              <tr v-if="!items.length && !loading">
                <td colspan="5" class="px-4 py-12 text-center text-xs text-slate-400">当日暂无数据（或尚未运行任务）</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="flex shrink-0 items-center justify-between text-[11.5px] text-slate-400">
        <span>共 {{ total }} 条 · 第 {{ page }} / {{ totalPages }} 页</span>
        <div class="flex items-center gap-1.5">
          <button class="h-7 w-7 rounded border border-slate-200 text-slate-400 hover:bg-slate-50 disabled:opacity-40" :disabled="page <= 1" @click="page--; load()">‹</button>
          <span class="px-1 text-slate-600">{{ page }}</span>
          <button class="h-7 w-7 rounded border border-slate-200 text-slate-400 hover:bg-slate-50 disabled:opacity-40" :disabled="page >= totalPages" @click="page++; load()">›</button>
        </div>
      </div>
    </template>

    <!-- ============ 趋势分析 ============ -->
    <div v-if="mode === 'trends'" class="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
      <!-- 关键词热度热力 -->
      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-slate-900">关键词热度 · 近 {{ trends.days.length }} 天</h3>
          <span class="text-[11px] text-slate-400">{{ trendsLoading ? '加载中…' : '数值为词表关键词当日匹配条数' }}</span>
        </div>
        <p v-if="!trends.keywords.length" class="py-6 text-center text-xs text-slate-400">{{ trendsLoading ? '正在加载趋势数据…' : '暂无趋势数据' }}</p>
        <div v-else class="space-y-1.5">
          <div class="flex gap-1.5 pl-[92px]">
            <span v-for="d in trends.days" :key="d" class="flex-1 text-center font-mono text-[9.5px] text-slate-400">{{ d.slice(5) }}</span>
          </div>
          <div v-for="kw in trends.keywords" :key="kw.word" class="flex items-center gap-1.5">
            <span class="w-[86px] shrink-0 truncate text-right text-xs text-slate-600" :title="kw.word">{{ kw.word }}</span>
            <div
              v-for="(v, i) in kw.values"
              :key="i"
              class="flex h-8 flex-1 items-center justify-center rounded text-[10.5px] font-semibold"
              :style="heatStyle(v, maxKeyword)"
              :class="v > 0 ? 'text-white' : 'text-slate-300'"
            >
              {{ v > 0 ? v : '' }}
            </div>
          </div>
        </div>
      </section>

      <div class="flex gap-4">
        <!-- 平台对比 -->
        <section class="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white p-5">
          <h3 class="mb-4 text-sm font-semibold text-slate-900">平台每日条数（近 {{ trends.days.length }} 天合计）</h3>
          <p v-if="!trends.platforms.length" class="py-6 text-center text-xs text-slate-400">暂无数据</p>
          <div v-else class="space-y-3">
            <div v-for="p in trends.platforms.slice(0, 8)" :key="p.id" class="flex items-center gap-3">
              <span class="w-20 shrink-0 truncate text-xs text-slate-600" :title="p.name">{{ p.name }}</span>
              <div class="h-2.5 flex-1 rounded-full bg-slate-100">
                <div class="h-2.5 rounded-full bg-blue-500" :style="{ width: `${(sum(p.values) / maxPlatform) * 100}%` }" />
              </div>
              <span class="w-8 shrink-0 text-right text-[11px] text-slate-400">{{ sum(p.values) }}</span>
            </div>
          </div>
        </section>

        <!-- 源健康热力 -->
        <section class="w-[460px] shrink-0 rounded-xl border border-slate-200 bg-white p-5">
          <h3 class="mb-4 text-sm font-semibold text-slate-900">数据源健康度</h3>
          <p v-if="!health.platforms.length" class="py-6 text-center text-xs text-slate-400">暂无抓取记录</p>
          <div v-else class="space-y-1.5">
            <div class="flex gap-1.5 pl-[72px]">
              <span v-for="d in health.days" :key="d" class="flex-1 text-center font-mono text-[9.5px] text-slate-400">{{ d.slice(5) }}</span>
            </div>
            <div v-for="p in health.platforms" :key="p.id" class="flex items-center gap-1.5">
              <span class="w-[66px] shrink-0 truncate text-right text-[11px] text-slate-600" :title="p.name">{{ p.name }}</span>
              <div
                v-for="(v, i) in p.values"
                :key="i"
                class="h-6 flex-1 rounded"
                :style="healthStyle(v)"
                :title="v === null ? '无数据' : `成功率 ${(v * 100).toFixed(0)}%`"
              />
            </div>
            <div class="flex items-center gap-4 pt-2 text-[10.5px] text-slate-400">
              <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded bg-emerald-500" />≥95%</span>
              <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded bg-amber-500" />70-95%</span>
              <span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded bg-red-500" />&lt;70%</span>
            </div>
          </div>
        </section>
      </div>

      <!-- 同源分析（MCP AnalyticsTools 口径） -->
      <div class="flex gap-4">
        <!-- 关键词共现 -->
        <section class="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white p-5">
          <div class="mb-3.5 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-900">关键词共现</h3>
            <span class="text-[10.5px] text-slate-400">与 MCP 分析同源</span>
          </div>
          <p v-if="!cooc.data.length" class="py-5 text-center text-xs text-slate-400">{{ trendsLoading ? '加载中…' : '暂无明显共现（需更多数据）' }}</p>
          <div v-else class="flex flex-wrap gap-2">
            <span
              v-for="(pair, i) in cooc.data"
              :key="i"
              class="inline-flex items-center gap-1.5 rounded-full bg-violet-50 px-3 py-1.5 text-xs text-violet-700"
              :style="{ fontSize: `${Math.min(15, 11 + pair.cooccurrence_count)}px` }"
              :title="pair.sample_titles?.[0] || ''"
            >
              {{ pair.keyword1 }} <span class="text-violet-400">↔</span> {{ pair.keyword2 }}
              <span class="text-[10px] text-violet-400">{{ pair.cooccurrence_count }} 次</span>
            </span>
          </div>
        </section>

        <!-- 异动信号 -->
        <section class="w-[460px] shrink-0 rounded-xl border border-slate-200 bg-white p-5">
          <div class="mb-3.5 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-900">异动信号</h3>
            <span class="text-[10.5px] text-slate-400">热度突增 ≥{{ viral.summary?.threshold ?? 3 }} 倍预警</span>
          </div>
          <p v-if="!viral.data.length" class="py-5 text-center text-xs text-slate-400">
            {{ viral.message || '暂无异动话题（数据随运行天数累积生效）' }}
          </p>
          <div v-else class="space-y-2">
            <div v-for="(t, i) in viral.data.slice(0, 5)" :key="i" class="flex items-start gap-2.5 rounded-lg bg-emerald-50/70 px-3 py-2">
              <TrendingUp :size="14" class="mt-0.5 shrink-0 text-emerald-600" />
              <div class="min-w-0">
                <p class="truncate text-xs font-medium text-slate-800">{{ t.topic || t.keyword || t.title }}</p>
                <p class="text-[10.5px] text-slate-500">热度 {{ t.old_frequency ?? t.previous ?? '?' }} → {{ t.new_frequency ?? t.current ?? '?' }}</p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { RefreshCw, TrendingUp } from 'lucide-vue-next'
import { api } from '../api/client'

const modes = [
  { key: 'news', label: '热榜查询' },
  { key: 'trends', label: '趋势分析' },
]
const mode = ref('news')

/* ---- 热榜查询 ---- */
const dates = ref([])
const date = ref('')
const keyword = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 50
const loading = ref(false)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

/** 时间串格式化。 @param {string} raw */
const fmt = (raw) => {
  if (!raw) return '—'
  const d = new Date(raw.replace(' ', 'T'))
  return Number.isNaN(d.getTime()) ? String(raw).slice(-8, -3) || String(raw) : d.toLocaleTimeString('zh-CN', { hour12: false })
}

/** 拉取当前页。 */
const load = async () => {
  loading.value = true
  try {
    const params = new URLSearchParams({ date: date.value, limit: String(pageSize), offset: String((page.value - 1) * pageSize) })
    if (keyword.value) params.set('q', keyword.value)
    const data = await api(`/api/v1/data/news?${params}`)
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}
const search = () => {
  page.value = 1
  load()
}

/* ---- 趋势分析 ---- */
const trends = ref({ days: [], keywords: [], platforms: [] })
const health = ref({ days: [], platforms: [] })
const cooc = ref({ data: [] })
const viral = ref({ data: [], summary: {}, message: '' })
const trendsLoaded = ref(false)
const trendsLoading = ref(false)
const maxKeyword = computed(() => Math.max(1, ...trends.value.keywords.flatMap((k) => k.values)))
const maxPlatform = computed(() => Math.max(1, ...trends.value.platforms.map((p) => sum(p.values))))

/** 求和。 @param {number[]} arr */
const sum = (arr) => (arr || []).reduce((a, b) => a + b, 0)

/** 热力块样式（蓝阶）。 @param {number} v @param {number} max */
const heatStyle = (v, max) => ({
  backgroundColor: v > 0 ? `rgba(37, 99, 235, ${0.25 + (v / max) * 0.7})` : '#F8FAFC',
})

/** 健康块样式（绿黄红）。 @param {number|null} v */
const healthStyle = (v) => {
  if (v === null || v === undefined) return { backgroundColor: '#F1F5F9' }
  if (v >= 0.95) return { backgroundColor: '#10B981' }
  if (v >= 0.7) return { backgroundColor: '#F59E0B' }
  return { backgroundColor: '#EF4444' }
}

/** 拉取全部趋势数据（loaded 标记避免重复请求，刷新按钮强制重载）。 */
const loadTrends = async (force = false) => {
  if (trendsLoading.value || (trendsLoaded.value && !force)) return
  trendsLoading.value = true
  try {
    const [kw, pl, h, co, vi] = await Promise.all([
      api('/api/v1/data/trends/keywords'),
      api('/api/v1/data/trends/platforms'),
      api('/api/v1/data/platforms/health'),
      api('/api/v1/data/trends/cooccurrence').catch(() => ({ data: [] })),
      api('/api/v1/data/trends/viral').catch(() => ({ data: [], summary: {}, message: '' })),
    ])
    trends.value = { ...kw, platforms: pl.platforms }
    health.value = h
    cooc.value = co
    viral.value = vi
    trendsLoaded.value = true
  } finally {
    trendsLoading.value = false
  }
}

watch(mode, (m) => {
  if (m === 'trends') loadTrends()
})

onMounted(async () => {
  loadTrends()
  const d = await api('/api/v1/data/dates')
  dates.value = d.dates
  date.value = d.dates[0] || ''
  if (date.value) load()
})
</script>
