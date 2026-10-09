<template>
  <div class="flex h-full gap-4">
    <!-- 报告列表 -->
    <div class="flex w-[320px] shrink-0 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white p-4">
      <h3 class="mb-3 text-[13px] font-semibold text-slate-900">历史报告</h3>
      <div class="min-h-0 flex-1 space-y-1.5 overflow-y-auto">
        <button
          v-for="r in reports"
          :key="r.path"
          class="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-left transition"
          :class="selected?.path === r.path ? 'bg-blue-50' : 'hover:bg-slate-50'"
          @click="selected = r"
        >
          <span
            class="shrink-0 rounded px-2 py-0.5 text-[10.5px] font-semibold"
            :class="r.mode === 'daily' ? 'bg-violet-50 text-violet-600' : 'bg-blue-50 text-blue-600'"
          >
            {{ r.mode }}
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-xs font-medium text-slate-800">{{ r.date }} {{ r.time }}</span>
          </span>
          <ChevronRight :size="14" class="shrink-0 text-slate-300" />
        </button>
        <p v-if="!reports.length && !loading" class="py-8 text-center text-xs text-slate-400">
          暂无报告，任务生成后自动出现
        </p>
      </div>
    </div>

    <!-- 预览区 -->
    <div class="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white">
      <div class="flex shrink-0 items-center justify-between border-b border-slate-100 bg-slate-50 px-5 py-3">
        <div>
          <p class="text-xs font-semibold text-slate-800">
            TrendRadar 热点报告 · {{ selected ? `${selected.date} ${selected.time}` : '未选择' }}
          </p>
          <p v-if="selected" class="font-mono text-[10.5px] text-slate-400">output/html/{{ selected.date }}/{{ selected.time.replace(':', '-') }}.html</p>
        </div>
        <a
          v-if="selected"
          :href="selected.path"
          target="_blank"
          class="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:underline"
        >
          <ExternalLink :size="13" /> 新窗口打开
        </a>
      </div>
      <iframe v-if="selected" :src="selected.path" class="min-h-0 flex-1 bg-white" title="报告预览" />
      <div v-else class="flex flex-1 flex-col items-center justify-center gap-2 text-slate-400">
        <FileText :size="32" />
        <p class="text-xs">选择左侧任意报告进行预览</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ChevronRight, ExternalLink, FileText } from 'lucide-vue-next'
import { api } from '../api/client'

const reports = ref([])
const selected = ref(null)
const loading = ref(true)

onMounted(async () => {
  try {
    reports.value = await api('/api/v1/reports')
    selected.value = reports.value[0] || null
  } finally {
    loading.value = false
  }
})
</script>
