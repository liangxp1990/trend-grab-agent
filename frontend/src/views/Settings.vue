<template>
  <div class="space-y-4 pb-2">
    <!-- 上排：账户 / 存储 / 版本（对应 .pen Screen Settings TopCards） -->
    <div class="grid gap-4 md:grid-cols-3">
      <!-- 账户 -->
      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <h3 class="mb-4 text-sm font-semibold text-slate-900">账户</h3>
        <div class="mb-4 flex items-center gap-3">
          <div class="flex h-11 w-11 items-center justify-center rounded-full bg-blue-700 text-lg font-semibold text-white">
            {{ auth.username.charAt(0).toUpperCase() }}
          </div>
          <div>
            <p class="text-sm font-semibold text-slate-900">{{ auth.username }}</p>
            <p class="text-[11px] text-slate-400">管理员 · 单用户模式（users 表已预留多用户）</p>
          </div>
        </div>
        <template v-if="!changingPw">
          <button class="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50" @click="changingPw = true">
            <KeyRound :size="13" /> 修改密码
          </button>
        </template>
        <div v-else class="space-y-2.5">
          <input v-model="pwForm.old" type="password" placeholder="当前密码" class="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs outline-none focus:border-blue-500" />
          <input v-model="pwForm.next" type="password" placeholder="新密码（至少 8 位）" class="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs outline-none focus:border-blue-500" />
          <input v-model="pwForm.confirm" type="password" placeholder="确认新密码" class="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs outline-none focus:border-blue-500" />
          <p v-if="pwMessage" :class="pwOk ? 'text-emerald-600' : 'text-red-500'" class="text-[11px]">{{ pwMessage }}</p>
          <div class="flex gap-2">
            <button class="flex-1 rounded-lg bg-blue-600 py-2 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-60" :disabled="pwSaving" @click="submitPw">
              {{ pwSaving ? '提交中…' : '确认修改' }}
            </button>
            <button class="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-500 hover:bg-slate-50" @click="changingPw = false">取消</button>
          </div>
        </div>
      </section>

      <!-- 存储 -->
      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <h3 class="mb-4 text-sm font-semibold text-slate-900">存储</h3>
        <div class="mb-3.5 flex items-center gap-2.5">
          <Database :size="16" class="text-emerald-600" />
          <div class="min-w-0">
            <p class="text-xs font-medium text-slate-800">本地 SQLite（后端：{{ storage.backend || '…' }}）</p>
            <p class="text-[11px] text-slate-400">
              {{ storage.local ? `${fmtBytes(storage.local.bytes)} · ${storage.local.db_count} 个日库 · 最新 ${storage.local.latest_db || '—'} · 保留 ${storage.local.retention}` : '加载中…' }}
            </p>
          </div>
        </div>
        <div class="mb-4 flex items-center gap-2.5">
          <Cloud :size="16" class="text-slate-400" />
          <div class="min-w-0 flex-1">
            <p class="text-xs font-medium" :class="storage.remote?.configured ? 'text-slate-800' : 'text-slate-500'">远程 S3 兼容存储（{{ storage.remote?.configured ? '已配置' : '未启用' }}）</p>
            <p class="text-[11px] text-slate-400">支持 R2 / OSS / COS / MinIO</p>
          </div>
          <span v-if="storage.remote?.configured" class="text-xs text-emerald-600">✓</span>
        </div>
        <p class="rounded-md bg-blue-50 px-2.5 py-2 text-[10.5px] leading-relaxed text-blue-700">
          存储后端与凭据在「配置管理」中调整；环境变量 S3_* 优先于配置文件。
        </p>
      </section>

      <!-- 版本 -->
      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <h3 class="mb-4 text-sm font-semibold text-slate-900">版本</h3>
        <div v-for="v in versionRows" :key="v.label" class="flex items-center gap-2 border-b border-slate-50 py-2 last:border-0">
          <component :is="v.ok ? CircleCheck : GitBranch" :size="13" :class="v.ok ? 'text-emerald-600' : 'text-slate-400'" />
          <span class="text-xs text-slate-600">{{ v.label }}</span>
          <span class="ml-auto text-[11.5px]" :class="v.ok ? 'text-slate-500' : 'font-semibold text-slate-800'">{{ v.value }}</span>
        </div>
      </section>
    </div>

    <!-- MCP 接入配置 -->
    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 class="text-sm font-semibold text-slate-900">MCP Server 接入</h3>
          <p class="mt-0.5 text-[11px] text-slate-400">复制 JSON 到 Cursor / Cline / Cherry Studio 等 AI 客户端的 MCP 配置中</p>
        </div>
        <div class="flex gap-1 rounded-lg border border-slate-200 p-1">
          <button
            v-for="m in mcpModes"
            :key="m.key"
            class="rounded-md px-3 py-1 text-[11px] font-medium transition"
            :class="mcpMode === m.key ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:text-slate-700'"
            @click="mcpMode = m.key"
          >
            {{ m.label }}
          </button>
        </div>
      </div>

      <!-- API Key 管理行（HTTP 模式） -->
      <div v-if="mcpMode === 'http'" class="mb-3 flex flex-wrap items-center gap-2.5 rounded-lg bg-amber-50/70 px-3.5 py-2.5">
        <ShieldCheck :size="14" class="shrink-0 text-amber-600" />
        <span class="text-[11.5px] text-amber-800">API Key 鉴权</span>
        <code class="min-w-0 flex-1 truncate rounded bg-white px-2 py-1 font-mono text-[11px] text-slate-700" :title="mcpKey.api_key">
          {{ mcpKey.api_key ? mcpKey.api_key : '（未生成）' }}
        </code>
        <button
          class="inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-white px-2.5 py-1 text-[11px] font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-60"
          :disabled="regenerating"
          @click="regenKey"
        >
          <RefreshCw :size="11" /> {{ regenerating ? '生成中…' : '重新生成' }}
        </button>
      </div>

      <div class="relative">
        <button
          class="absolute right-2.5 top-2.5 inline-flex items-center gap-1.5 rounded-md bg-white/90 px-2.5 py-1 text-[11px] font-medium text-slate-600 shadow-sm ring-1 ring-slate-200 transition hover:text-blue-600"
          @click="copyMcpJson"
        >
          <component :is="copied ? CircleCheck : Copy" :size="12" :class="copied ? 'text-emerald-600' : ''" />
          {{ copied ? '已复制' : '复制 JSON' }}
        </button>
        <pre class="max-h-56 overflow-auto rounded-lg bg-[#0D1424] p-4 pr-24 font-mono text-[11.5px] leading-relaxed text-slate-300">{{ mcpJson }}</pre>
      </div>
      <p class="mt-2 text-[10.5px] text-slate-400">{{ currentMcpMode.note }}</p>
    </section>

    <!-- 审计日志（对应 .pen AuditCard） -->
    <section class="rounded-xl border border-slate-200 bg-white p-5">
      <div class="mb-3 flex items-center justify-between">
        <h3 class="text-sm font-semibold text-slate-900">审计日志</h3>
        <span class="text-[11px] text-slate-400">共 {{ audit.total }} 条</span>
      </div>
      <div class="max-h-[380px] overflow-auto rounded-lg border border-slate-100">
        <table class="w-full text-left">
          <thead>
            <tr class="bg-slate-50 text-[11px] font-semibold text-slate-500">
              <th class="px-4 py-2">时间</th>
              <th class="px-4 py-2">用户</th>
              <th class="px-4 py-2">操作</th>
              <th class="px-4 py-2">详情</th>
              <th class="px-4 py-2">IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(a, i) in audit.items" :key="i" class="border-t border-slate-50 text-[12px]">
              <td class="px-4 py-2.5 text-slate-500">{{ fmtDate(a.time) }}</td>
              <td class="px-4 py-2.5 text-slate-600">{{ a.username || '—' }}</td>
              <td class="px-4 py-2.5">
                <span class="rounded bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-600">{{ a.action }}</span>
              </td>
              <td class="max-w-0 truncate px-4 py-2.5 text-slate-600" :title="a.detail">{{ a.detail || '—' }}</td>
              <td class="px-4 py-2.5 font-mono text-[11px] text-slate-400">{{ a.ip }}</td>
            </tr>
            <tr v-if="!audit.items.length">
              <td colspan="5" class="px-4 py-8 text-center text-xs text-slate-400">暂无审计记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { KeyRound, Database, Cloud, CircleCheck, GitBranch, Copy, ShieldCheck, RefreshCw } from 'lucide-vue-next'
import { api } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const status = ref(null)
const storage = ref({})
const configInfo = ref(null)
const audit = ref({ total: 0, items: [] })

const versionRows = computed(() => {
  const v = status.value?.versions || {}
  return [
    { label: '引擎 TrendRadar', value: `${v.engine || '—'} 最新`, ok: true },
    { label: 'MCP Server', value: `${v.mcp || '—'} 最新`, ok: true },
    { label: '管理平台', value: v.webapp || '—', ok: true },
    { label: '当前配置版本', value: configInfo.value ? `v${configInfo.value.version}` : '—', ok: false },
  ]
})

/* ---- 修改密码 ---- */
const changingPw = ref(false)
const pwForm = reactive({ old: '', next: '', confirm: '' })
const pwMessage = ref('')
const pwOk = ref(false)
const pwSaving = ref(false)

const submitPw = async () => {
  pwMessage.value = ''
  if (pwForm.next.length < 8) {
    pwOk.value = false
    pwMessage.value = '新密码至少 8 位'
    return
  }
  if (pwForm.next !== pwForm.confirm) {
    pwOk.value = false
    pwMessage.value = '两次输入的新密码不一致'
    return
  }
  pwSaving.value = true
  try {
    const result = await api('/api/v1/auth/password', {
      method: 'PUT',
      body: JSON.stringify({ old_password: pwForm.old, new_password: pwForm.next }),
    })
    pwOk.value = true
    pwMessage.value = result.message
    setTimeout(() => {
      changingPw.value = false
      pwForm.old = pwForm.next = pwForm.confirm = ''
      pwMessage.value = ''
    }, 1500)
  } catch (e) {
    pwOk.value = false
    pwMessage.value = e.message
  } finally {
    pwSaving.value = false
  }
}

/* ---- MCP 接入配置 ---- */
const mcpModes = [
  {
    key: 'http',
    label: 'HTTP（Docker 部署）',
    note: '需运行 docker-compose-web.yml（含 trendradar-mcp 容器，端口 3333）。所有请求需携带 API Key（上方 JSON 已自动包含 headers）；重新生成 Key 后需重启 MCP 容器。',
  },
  {
    key: 'stdio',
    label: 'stdio（本地运行）',
    note: '需先 pip install . 安装引擎与 MCP 包（提供 trendradar-mcp 命令）。本地进程模式不启用 Key 鉴权（本机信任环境）。',
  },
]
const mcpMode = ref('http')
const currentMcpMode = computed(() => mcpModes.find((m) => m.key === mcpMode.value))

/* ---- MCP API Key ---- */
const mcpKey = ref({ api_key: '', source: 'none' })
const regenerating = ref(false)

/** 重新生成 Key。 */
const regenKey = async () => {
  regenerating.value = true
  try {
    mcpKey.value = await api('/api/v1/system/mcp-key/regenerate', { method: 'POST' })
  } catch (e) {
    /* 生成失败静默，key 保持旧值 */
  } finally {
    regenerating.value = false
  }
}

const mcpJson = computed(() => {
  const host = location.hostname || '127.0.0.1'
  if (mcpMode.value === 'http') {
    const entry = { url: `http://${host}:3333/mcp` }
    if (mcpKey.value.api_key) {
      entry.headers = { Authorization: `Bearer ${mcpKey.value.api_key}` }
    }
    return JSON.stringify({ mcpServers: { 'trendradar-news': entry } }, null, 2)
  }
  return JSON.stringify(
    {
      mcpServers: {
        'trendradar-news': {
          command: 'trendradar-mcp',
          env: { PROJECT_ROOT: '/path/to/trend-grab-agent' },
        },
      },
    },
    null,
    2
  )
})

/** 复制 MCP JSON 到剪贴板。 */
const copied = ref(false)
const copyMcpJson = async () => {
  try {
    await navigator.clipboard.writeText(mcpJson.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 1600)
  } catch {
    /* 剪贴板不可用时降级选中文本 */
    const range = document.createRange()
    const pre = document.querySelector('pre')
    if (pre) {
      range.selectNodeContents(pre)
      const selection = getSelection()
      selection?.removeAllRanges()
      selection?.addRange(range)
    }
  }
}

/** 字节数格式化。 @param {number} bytes */
const fmtBytes = (bytes) => (bytes >= 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`)

/** ISO 转本地短串。 @param {string} iso */
const fmtDate = (iso) =>
  new Date(iso).toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })

onMounted(async () => {
  const results = await Promise.allSettled([
    api('/api/v1/system/status'),
    api('/api/v1/system/storage'),
    api('/api/v1/config'),
    api('/api/v1/system/audit-logs?limit=30'),
  ])
  if (results[0].status === 'fulfilled') status.value = results[0].value
  api('/api/v1/system/mcp-key').then((k) => (mcpKey.value = k)).catch(() => {})
  if (results[1].status === 'fulfilled') storage.value = results[1].value
  if (results[2].status === 'fulfilled') configInfo.value = results[2].value
  if (results[3].status === 'fulfilled') audit.value = results[3].value
})
</script>
