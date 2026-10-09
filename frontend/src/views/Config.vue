<template>
  <div class="flex h-full flex-col gap-4">
    <!-- Tab 导航 + 全局保存 -->
    <div class="flex items-center justify-between">
      <div class="flex gap-1 rounded-lg border border-slate-200 bg-white p-1">
        <button
          v-for="t in tabs"
          :key="t.key"
          class="rounded-md px-3.5 py-1.5 text-xs font-medium transition"
          :class="tab === t.key ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:text-slate-700'"
          @click="tab = t.key"
        >
          {{ t.label }}
        </button>
      </div>
      <div class="flex items-center gap-3">
        <span v-if="savedAt" class="text-[11px] text-emerald-600">已保存 {{ savedAt }}</span>
        <button
          class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-[13px] font-medium text-white hover:bg-blue-700 disabled:opacity-60"
          :disabled="saving"
          @click="save"
        >
          <Save :size="14" /> {{ saving ? '保存中…' : '保存为新版本' }}
        </button>
      </div>
    </div>

    <p v-if="message" :class="isError ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-700'" class="rounded-lg px-4 py-2 text-xs">
      {{ message }}
    </p>

    <!-- ============ 数据源 ============ -->
    <div v-if="tab === 'sources' && cfg" class="min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <div class="mb-4 flex items-center gap-3">
          <h3 class="text-sm font-semibold text-slate-900">热榜平台</h3>
          <span class="text-xs text-slate-400">{{ enabledPlatforms.length }} / {{ allPlatforms.length }} 启用</span>
        </div>
        <div class="grid grid-cols-2 gap-3.5 md:grid-cols-4">
          <div
            v-for="p in allPlatforms"
            :key="p.id"
            class="rounded-lg border p-4 transition"
            :class="p.on ? 'border-slate-200 bg-white' : 'border-slate-100 bg-slate-50 opacity-70'"
          >
            <div class="flex items-start justify-between">
              <div>
                <p class="text-[13px] font-semibold text-slate-800">{{ p.name }}</p>
                <p class="mt-0.5 font-mono text-[10.5px] text-slate-400">{{ p.id }}</p>
              </div>
              <button
                class="h-[18px] w-8 rounded-full transition-colors"
                :class="p.on ? 'bg-emerald-500' : 'bg-slate-300'"
                @click="togglePlatform(p)"
              >
                <span class="block h-3.5 w-3.5 rounded-full bg-white transition-transform" :class="p.on ? 'translate-x-4' : 'translate-x-0.5'" />
              </button>
            </div>
          </div>
        </div>
      </section>

      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <div class="mb-3 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <h3 class="text-sm font-semibold text-slate-900">RSS 订阅源</h3>
            <span class="text-xs text-slate-400">{{ rssFeeds.filter((f) => f.enabled !== false).length }} 启用</span>
          </div>
          <button class="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50" @click="addFeed">
            <Plus :size="13" /> 添加源
          </button>
        </div>
        <div class="space-y-2">
          <div v-for="(f, i) in rssFeeds" :key="i" class="flex flex-wrap items-center gap-2.5 rounded-lg bg-slate-50 px-3.5 py-2.5">
            <button
              class="h-[18px] w-8 shrink-0 rounded-full transition-colors"
              :class="f.enabled !== false ? 'bg-emerald-500' : 'bg-slate-300'"
              @click="f.enabled = f.enabled === false"
            >
              <span class="block h-3.5 w-3.5 rounded-full bg-white transition-transform" :class="f.enabled !== false ? 'translate-x-4' : 'translate-x-0.5'" />
            </button>
            <input v-model="f.name" class="w-36 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs outline-none focus:border-blue-500" placeholder="名称" />
            <input v-model="f.url" class="min-w-[260px] flex-1 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-xs outline-none focus:border-blue-500" placeholder="https://…/feed.xml" />
            <input v-model.number="f.max_age_days" type="number" min="0" class="w-20 rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs outline-none focus:border-blue-500" title="新鲜度天数（0=不过滤）" />
            <button class="text-slate-400 hover:text-red-500" @click="rssFeeds.splice(i, 1)"><Trash2 :size="14" /></button>
          </div>
        </div>
      </section>
    </div>

    <!-- ============ 调度 ============ -->
    <div v-if="tab === 'schedule' && cfg" class="min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <div class="mb-4 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-slate-900">执行频率</h3>
          <span
            class="rounded-full px-2.5 py-0.5 text-[11px] font-medium"
            :class="schedule.enabled ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-400'"
          >
            {{ schedule.enabled ? '调度已启用' : '已停用' }}
          </span>
        </div>
        <p class="mb-3 text-[11.5px] text-slate-500">触发频率决定多久唤醒一次引擎；唤醒后的行为（采集/分析/推送时段）由 timeline.yaml 决定。</p>
        <div class="mb-4 flex flex-wrap gap-2">
          <button
            v-for="f in freqPresets"
            :key="f.cron"
            class="rounded-lg px-3.5 py-1.5 text-xs transition"
            :class="schedule.cron_expr === f.cron ? 'bg-blue-50 font-semibold text-blue-600 ring-1 ring-blue-500' : 'border border-slate-200 text-slate-500 hover:bg-slate-50'"
            @click="schedule.cron_expr = f.cron"
          >
            {{ f.label }}
          </button>
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <div class="flex items-center gap-2 rounded-lg border border-slate-200 px-3.5 py-2">
            <Timer :size="14" class="text-slate-400" />
            <input v-model="schedule.cron_expr" class="w-40 bg-transparent font-mono text-xs text-slate-800 outline-none" />
          </div>
          <button class="rounded-lg bg-blue-600 px-4 py-2 text-xs font-medium text-white hover:bg-blue-700" @click="saveSchedule">保存调度</button>
          <span v-if="nextRunText" class="text-[11.5px] text-slate-500">下次触发 {{ nextRunText }}</span>
        </div>
      </section>

      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <h3 class="mb-3 text-sm font-semibold text-slate-900">报告模式（默认值，可被 timeline 时段覆盖）</h3>
        <div class="flex flex-wrap items-center gap-x-8 gap-y-3">
          <div class="flex items-center gap-2.5">
            <span class="text-xs text-slate-600">模式</span>
            <div class="flex rounded-lg border border-slate-200 p-0.5">
              <button
                v-for="m in ['daily', 'current', 'incremental']"
                :key="m"
                class="rounded-md px-3 py-1 text-[11px]"
                :class="cfg.report.mode === m ? 'bg-blue-50 font-semibold text-blue-600' : 'text-slate-500'"
                @click="cfg.report.mode = m"
              >
                {{ m }}
              </button>
            </div>
          </div>
          <label class="flex items-center gap-2 text-xs text-slate-600">
            分组维度
            <div class="flex rounded-lg border border-slate-200 p-0.5">
              <button
                v-for="m in ['keyword', 'platform']"
                :key="m"
                class="rounded-md px-3 py-1 text-[11px]"
                :class="cfg.report.display_mode === m ? 'bg-blue-50 font-semibold text-blue-600' : 'text-slate-500'"
                @click="cfg.report.display_mode = m"
              >
                {{ m === 'keyword' ? '按词' : '按平台' }}
              </button>
            </div>
          </label>
        </div>
      </section>
    </div>

    <!-- ============ 筛选与展示 ============ -->
    <div v-if="tab === 'filter' && cfg" class="min-h-0 flex-1 space-y-5 overflow-y-auto pr-1">
      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <h3 class="mb-4 text-sm font-semibold text-slate-900">筛选策略</h3>
        <div class="grid gap-3 md:grid-cols-2">
          <button
            v-for="m in filterModes"
            :key="m.key"
            class="flex items-start gap-3 rounded-xl p-4 text-left transition"
            :class="cfg.filter.method === m.key ? 'bg-blue-50 ring-2 ring-blue-500' : 'border border-slate-200 hover:border-slate-300'"
            @click="cfg.filter.method = m.key"
          >
            <component :is="m.icon" :size="17" :class="cfg.filter.method === m.key ? 'text-blue-600' : 'text-slate-400'" />
            <div>
              <p class="text-sm font-semibold" :class="cfg.filter.method === m.key ? 'text-blue-700' : 'text-slate-800'">{{ m.label }}</p>
              <p class="mt-0.5 text-[11px] text-slate-500">{{ m.desc }}</p>
            </div>
          </button>
        </div>
      </section>

      <section class="rounded-xl border border-slate-200 bg-white p-5">
        <h3 class="mb-4 text-sm font-semibold text-slate-900">推送区域</h3>
        <div class="space-y-2">
          <div v-for="r in regionRows" :key="r.key" class="flex items-center gap-3 rounded-lg bg-slate-50 px-3.5 py-2.5">
            <GripVertical :size="14" class="text-slate-300" />
            <span class="w-14 text-center text-[11px] font-bold" :class="r.color">{{ r.index + 1 }}</span>
            <div class="min-w-0 flex-1">
              <p class="text-xs font-medium text-slate-800">{{ r.label }}</p>
              <p class="text-[10.5px] text-slate-400">{{ r.desc }}</p>
            </div>
            <button
              class="h-[18px] w-8 shrink-0 rounded-full transition-colors"
              :class="regions[r.key] ? 'bg-emerald-500' : 'bg-slate-300'"
              @click="regions[r.key] = !regions[r.key]"
            >
              <span class="block h-3.5 w-3.5 rounded-full bg-white transition-transform" :class="regions[r.key] ? 'translate-x-4' : 'translate-x-0.5'" />
            </button>
          </div>
        </div>
      </section>

      <section class="grid gap-4 md:grid-cols-2">
        <div class="rounded-xl border p-5" :class="cfg.filter.method === 'ai' ? 'border-blue-300 bg-blue-50/40' : 'border-slate-200 bg-white opacity-60'">
          <div class="mb-2 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-900">AI 兴趣描述</h3>
            <span class="font-mono text-[10px] text-slate-400">ai_interests.txt</span>
          </div>
          <textarea
            v-model="files['ai_interests.txt']"
            rows="9"
            class="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-[11.5px] leading-relaxed text-slate-700 outline-none focus:border-blue-500"
            :disabled="cfg.filter.method !== 'ai'"
          />
        </div>
        <div class="rounded-xl border p-5" :class="cfg.filter.method === 'keyword' ? 'border-blue-300 bg-blue-50/40' : 'border-slate-200 bg-white opacity-60'">
          <div class="mb-2 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-900">关键词词表</h3>
            <span class="font-mono text-[10px] text-slate-400">frequency_words.txt</span>
          </div>
          <textarea
            v-model="files['frequency_words.txt']"
            rows="9"
            class="w-full rounded-lg border border-slate-200 bg-slate-50 p-3 font-mono text-[11.5px] leading-relaxed text-slate-700 outline-none focus:border-blue-500"
            :disabled="cfg.filter.method !== 'keyword'"
          />
          <p class="mt-2 font-mono text-[10px] text-slate-400">+必须 · !排除 · @上限 · /正则/ · =&gt;别名 · [GLOBAL_FILTER]</p>
        </div>
      </section>
    </div>

    <!-- ============ AI 与通知 ============ -->
    <div v-if="tab === 'ai' && cfg" class="min-h-0 flex-1 gap-5 overflow-y-auto pr-1 md:flex">
      <div class="min-w-0 flex-1 space-y-5">
        <section class="rounded-xl border border-slate-200 bg-white p-5">
          <div class="mb-4 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-slate-900">AI 模型</h3>
            <span class="text-[11px] text-slate-400">LiteLLM 统一接口 · 100+ 提供商</span>
          </div>
          <div class="space-y-4">
            <!-- 提供商预设 -->
            <div>
              <span class="text-xs font-medium text-slate-600">提供商</span>
              <div class="mt-2 flex flex-wrap gap-2">
                <button
                  v-for="p in providers"
                  :key="p.id"
                  class="rounded-lg px-3.5 py-1.5 text-xs transition"
                  :class="providerId === p.id ? 'bg-blue-50 font-semibold text-blue-600 ring-1 ring-blue-500' : 'border border-slate-200 text-slate-500 hover:bg-slate-50'"
                  @click="selectProvider(p)"
                >
                  {{ p.label }}
                </button>
              </div>
              <p class="mt-2 text-[11px] text-slate-400">{{ currentProvider.note }}</p>
            </div>

            <!-- 模型（联想输入） -->
            <label class="block">
              <span class="text-xs font-medium text-slate-600">模型（provider/model 格式，可手输任意 LiteLLM 支持的模型）</span>
              <input
                v-model="cfg.ai.model"
                list="model-options"
                class="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs outline-none focus:border-blue-500"
                placeholder="deepseek/deepseek-chat"
              />
              <datalist id="model-options">
                <option v-for="m in currentProvider.models" :key="m" :value="m" />
              </datalist>
            </label>

            <!-- Key / Base -->
            <div class="grid gap-3.5 md:grid-cols-2">
              <label class="block">
                <span class="text-xs font-medium text-slate-600">API Key</span>
                <input v-model="cfg.ai.api_key" type="password" class="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs outline-none focus:border-blue-500" placeholder="未修改则保留原值" />
                <span class="mt-1 block text-[10.5px] text-slate-400">{{ currentProvider.keyHint }}</span>
              </label>
              <label class="block">
                <span class="text-xs font-medium text-slate-600">API Base（可选）</span>
                <input v-model="cfg.ai.api_base" class="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs outline-none focus:border-blue-500" :placeholder="currentProvider.basePlaceholder" />
              </label>
            </div>

            <!-- 生成参数 -->
            <div>
              <span class="text-xs font-medium text-slate-600">生成参数</span>
              <div class="mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
                <label v-for="p in aiParams" :key="p.key" class="block">
                  <span class="text-[10.5px] text-slate-500">{{ p.label }}</span>
                  <input
                    :value="getPath(cfg.ai, p.key)"
                    type="number"
                    :step="p.step"
                    class="mt-1 w-full rounded-md border border-slate-200 px-2.5 py-1.5 font-mono text-xs outline-none focus:border-blue-500"
                    @input="setPath(cfg.ai, p.key, Number($event.target.value))"
                  />
                </label>
              </div>
            </div>

            <!-- 备用模型链 -->
            <label class="block">
              <span class="text-xs font-medium text-slate-600">备用模型链（主模型失败时依次回退，逗号分隔）</span>
              <input v-model="fallbackText" class="mt-1.5 w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-xs outline-none focus:border-blue-500" placeholder="openai/gpt-4o-mini, openai/deepseek-ai/DeepSeek-V3" />
            </label>

            <!-- 测试连接 -->
            <div class="flex items-center gap-3 border-t border-slate-100 pt-3.5">
              <button
                class="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                :disabled="testingAi"
                @click="testAi"
              >
                <PlugZap :size="13" /> {{ testingAi ? '测试中…' : '测试连接' }}
              </button>
              <span v-if="aiTestResult" class="text-[11.5px]" :class="aiTestOk ? 'text-emerald-600' : 'text-red-500'">{{ aiTestResult }}</span>
              <span v-else class="text-[11px] text-slate-400">使用界面当前填写的值测试，无需先保存</span>
            </div>
          </div>
        </section>

        <section class="rounded-xl border border-slate-200 bg-white p-5">
          <h3 class="mb-3 text-sm font-semibold text-slate-900">智能功能</h3>
          <div v-for="f in aiFeatures" :key="f.key" class="flex items-center gap-3 border-b border-slate-50 py-2.5 last:border-0">
            <button
              class="h-[18px] w-8 shrink-0 rounded-full transition-colors"
              :class="getPath(cfg, f.key) ? 'bg-emerald-500' : 'bg-slate-300'"
              @click="setPath(cfg, f.key, !getPath(cfg, f.key))"
            >
              <span class="block h-3.5 w-3.5 rounded-full bg-white transition-transform" :class="getPath(cfg, f.key) ? 'translate-x-4' : 'translate-x-0.5'" />
            </button>
            <div class="min-w-0 flex-1">
              <p class="text-xs font-medium text-slate-800">{{ f.label }}</p>
              <p class="text-[10.5px] text-slate-400">{{ f.desc }}</p>
            </div>
          </div>
        </section>
      </div>

      <div class="w-[420px] shrink-0 space-y-5">
        <section class="rounded-xl border border-slate-200 bg-white p-5">
          <h3 class="mb-1 text-sm font-semibold text-slate-900">通知渠道</h3>
          <p class="mb-3 text-[11px] text-slate-400">留空 / 保持掩码不变即不修改；多账号用分号分隔</p>
          <div class="space-y-4">
            <div v-for="ch in channelForms" :key="ch.key" class="rounded-lg bg-slate-50 p-3.5">
              <p class="mb-2 text-xs font-semibold text-slate-700">{{ ch.label }}</p>
              <label v-for="f in ch.fields" :key="f.key" class="mb-1.5 block last:mb-0">
                <span class="text-[10.5px] text-slate-500">{{ f.label }}</span>
                <input
                  v-model="ch.values[f.key]"
                  :type="f.secret ? 'password' : 'text'"
                  class="mt-1 w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-[11px] outline-none focus:border-blue-500"
                  :placeholder="f.secret ? '未修改则保留原值' : ''"
                />
              </label>
            </div>
          </div>
        </section>
      </div>
    </div>

    <!-- ============ 版本历史 ============ -->
    <div v-if="tab === 'versions'" class="min-h-0 flex-1 gap-4 overflow-hidden pr-1 md:flex">
      <div class="w-[320px] shrink-0 space-y-2.5 overflow-y-auto pr-1">
        <div
          v-for="v in versions"
          :key="v.id"
          class="cursor-pointer rounded-xl border p-4 transition"
          :class="selectedVersion?.id === v.id ? 'border-blue-500 ring-2 ring-blue-200' : v.is_active ? 'border-blue-300 bg-blue-50/60' : 'border-slate-200 bg-white hover:border-slate-300'"
          @click="loadDiff(v)"
        >
          <div class="mb-1.5 flex items-center gap-2">
            <span class="text-sm font-bold" :class="v.is_active ? 'text-blue-700' : 'text-slate-800'">v{{ v.version }}</span>
            <span v-if="v.is_active" class="rounded-full bg-blue-600 px-2 py-0.5 text-[9.5px] font-semibold text-white">当前生效</span>
            <span class="ml-auto text-[10.5px] text-slate-400">{{ fmtDate(v.created_at) }}</span>
          </div>
          <p class="text-xs text-slate-600">{{ v.comment || '（无备注）' }}</p>
          <div class="mt-2.5 flex items-center justify-between">
            <span class="text-[10.5px] text-slate-400">{{ v.created_by }}</span>
            <button
              v-if="!v.is_active"
              class="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 py-1 text-[11px] text-slate-600 hover:bg-slate-50"
              @click.stop="rollback(v)"
            >
              <Undo2 :size="11" /> 回滚
            </button>
          </div>
        </div>
        <p v-if="!versions.length" class="py-8 text-center text-xs text-slate-400">暂无版本</p>
      </div>

      <!-- Diff 面板 -->
      <div class="min-w-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-5">
        <template v-if="diffData">
          <div class="mb-4 flex flex-wrap items-center gap-3">
            <h3 class="text-sm font-semibold text-slate-900">
              版本对比：v{{ diffData.base.version }} → v{{ diffData.target.version }}
            </h3>
            <div class="flex gap-1.5">
              <span v-if="diffData.summary.added" class="rounded bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-600">+{{ diffData.summary.added }}</span>
              <span v-if="diffData.summary.removed" class="rounded bg-red-50 px-2 py-0.5 text-[11px] font-medium text-red-600">−{{ diffData.summary.removed }}</span>
              <span v-if="diffData.summary.changed" class="rounded bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-600">~{{ diffData.summary.changed }}</span>
            </div>
          </div>
          <p v-if="!diffData.changes.length && !diffData.files_added.length && !diffData.files_removed.length" class="py-8 text-center text-xs text-slate-400">
            两个版本的配置内容完全一致
          </p>
          <div v-else class="space-y-1">
            <div
              v-for="(c, i) in diffData.changes"
              :key="i"
              class="rounded-lg px-3 py-2 font-mono text-[11px] leading-relaxed"
              :class="c.kind === 'added' ? 'bg-emerald-50' : c.kind === 'removed' ? 'bg-red-50' : 'bg-slate-50'"
            >
              <div class="flex items-center gap-2">
                <span class="font-bold" :class="c.kind === 'added' ? 'text-emerald-600' : c.kind === 'removed' ? 'text-red-600' : 'text-blue-600'">
                  {{ c.kind === 'added' ? '+' : c.kind === 'removed' ? '−' : '~' }}
                </span>
                <span class="min-w-0 flex-1 truncate text-slate-700" :title="c.path">{{ c.path }}</span>
              </div>
              <div v-if="c.old !== null" class="truncate pl-5 text-red-500/80">− {{ c.old }}</div>
              <div v-if="c.new !== null" class="truncate pl-5 text-emerald-700">+ {{ c.new }}</div>
            </div>
            <div v-for="f in diffData.files_added" :key="'fa-' + f" class="rounded-lg bg-emerald-50 px-3 py-2 font-mono text-[11px] text-emerald-700">+ 文件 {{ f }}</div>
            <div v-for="f in diffData.files_removed" :key="'fr-' + f" class="rounded-lg bg-red-50 px-3 py-2 font-mono text-[11px] text-red-600">− 文件 {{ f }}</div>
          </div>
        </template>
        <div v-else class="flex h-full flex-col items-center justify-center gap-2 text-slate-400">
          <GitCompareArrows :size="30" />
          <p class="text-xs">点击左侧版本卡片，查看与其前一版本的对比</p>
          <p class="text-[10.5px] text-slate-300">敏感值在对比中掩码展示 · 完整变更见审计日志</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Save, Plus, Trash2, Timer, GripVertical, Undo2, ListFilter, Sparkles, PlugZap, GitCompareArrows } from 'lucide-vue-next'
import { api } from '../api/client'

const tabs = [
  { key: 'sources', label: '数据源' },
  { key: 'schedule', label: '调度' },
  { key: 'filter', label: '筛选与展示' },
  { key: 'ai', label: 'AI 与通知' },
  { key: 'versions', label: '版本历史' },
]
const tab = ref('sources')
const cfg = ref(null)
const files = reactive({})
const versions = ref([])
const schedule = reactive({ cron_expr: '', enabled: true, next_run: null })
const message = ref('')
const isError = ref(false)
const saving = ref(false)
const savedAt = ref('')

const freqPresets = [
  { label: '每 15 分钟', cron: '*/15 * * * *' },
  { label: '每 30 分钟', cron: '*/30 * * * *' },
  { label: '每小时', cron: '0 * * * *' },
  { label: '每天 08:00', cron: '0 8 * * *' },
]
const filterModes = [
  { key: 'keyword', label: '关键词匹配', desc: '词表驱动 · 零 token 消耗 · 结果完全可预期', icon: ListFilter },
  { key: 'ai', label: 'AI 智能筛选', desc: '兴趣标签分类 · min_score 0.7 · 失败自动回退关键词', icon: Sparkles },
]
const aiFeatures = [
  { key: 'ai_analysis.enabled', label: 'AI 深度分析', desc: '五板块报告 · 单次 150 条上限' },
  { key: 'ai_translation.enabled', label: 'AI 翻译', desc: '目标语言中文 · 范围 RSS + 独立展示区' },
]

/** LiteLLM 常用提供商预设（完整列表 docs.litellm.ai/docs/providers）。 */
const providers = [
  {
    id: 'deepseek', label: 'DeepSeek', prefix: 'deepseek/',
    models: ['deepseek/deepseek-chat', 'deepseek/deepseek-reasoner'],
    keyHint: 'platform.deepseek.com 获取（sk- 开头）', basePlaceholder: '',
    note: '性价比默认选择 · 每天约 0.1-0.2 元（默认推送频率）',
  },
  {
    id: 'openai', label: 'OpenAI', prefix: 'openai/',
    models: ['openai/gpt-4o', 'openai/gpt-4o-mini', 'openai/gpt-4.1'],
    keyHint: 'platform.openai.com 获取（sk- 开头）', basePlaceholder: '',
    note: '官方 OpenAI 接口',
  },
  {
    id: 'gemini', label: 'Gemini', prefix: 'gemini/',
    models: ['gemini/gemini-2.5-flash', 'gemini/gemini-2.5-pro', 'gemini/gemini-2.0-flash'],
    keyHint: 'aistudio.google.com 获取', basePlaceholder: '',
    note: 'Google AI Studio 免费额度可用',
  },
  {
    id: 'anthropic', label: 'Claude', prefix: 'anthropic/',
    models: ['anthropic/claude-3-5-sonnet', 'anthropic/claude-3-5-haiku', 'anthropic/claude-sonnet-4'],
    keyHint: 'console.anthropic.com 获取（sk-ant- 开头）', basePlaceholder: '',
    note: 'Anthropic 官方接口',
  },
  {
    id: 'ollama', label: 'Ollama 本地', prefix: 'ollama/',
    models: ['ollama/llama3', 'ollama/qwen2.5', 'ollama/deepseek-r1'],
    keyHint: '本地运行无需 API Key（填任意非空值如 ollama）', basePlaceholder: 'http://localhost:11434',
    note: '本地零成本 · 需先安装 Ollama 并拉取模型',
  },
  {
    id: 'custom', label: 'OpenAI 兼容端点', prefix: 'openai/',
    models: [],
    keyHint: '服务商提供的 Key', basePlaceholder: 'https://api.example.com/v1',
    note: '接入任意兼容 OpenAI 协议的服务商：模型填 openai/实际模型名（openai/ 前缀强制使用 OpenAI 协议），API Base 填端点地址',
  },
]
const providerId = ref('custom')
const currentProvider = computed(() => providers.find((p) => p.id === providerId.value) || providers[providers.length - 1])

/** 选择提供商：联动模型名与默认 Base。 @param {object} p */
const selectProvider = (p) => {
  providerId.value = p.id
  if (!cfg.value.ai.model || !cfg.value.ai.model.startsWith(p.prefix)) {
    cfg.value.ai.model = p.models[0] || p.prefix
  }
  if (p.id === 'ollama' && !cfg.value.ai.api_base) cfg.value.ai.api_base = p.basePlaceholder
}

const aiParams = [
  { key: 'temperature', label: 'temperature', step: 0.1 },
  { key: 'max_tokens', label: 'max_tokens', step: 100 },
  { key: 'timeout', label: '超时（秒）', step: 10 },
  { key: 'num_retries', label: '重试次数', step: 1 },
]

/** 备用模型链：数组 ↔ 逗号分隔文本。 */
const fallbackText = ref('')
const channelForms = [
  { key: 'feishu', label: '飞书', values: {}, fields: [{ key: 'webhook_url', label: 'Webhook URL', secret: true }] },
  { key: 'dingtalk', label: '钉钉', values: {}, fields: [{ key: 'webhook_url', label: 'Webhook URL', secret: true }] },
  { key: 'wework', label: '企业微信', values: {}, fields: [{ key: 'webhook_url', label: 'Webhook URL', secret: true }] },
  { key: 'telegram', label: 'Telegram', values: {}, fields: [{ key: 'bot_token', label: 'Bot Token', secret: true }, { key: 'chat_id', label: 'Chat ID' }] },
  { key: 'email', label: '邮件', values: {}, fields: [{ key: 'from', label: '发件人' }, { key: 'password', label: '密码/授权码', secret: true }, { key: 'to', label: '收件人（逗号分隔）' }] },
  { key: 'ntfy', label: 'ntfy', values: {}, fields: [{ key: 'server_url', label: '服务器' }, { key: 'topic', label: 'Topic' }] },
  { key: 'bark', label: 'Bark', values: {}, fields: [{ key: 'url', label: '推送 URL', secret: true }] },
  { key: 'slack', label: 'Slack', values: {}, fields: [{ key: 'webhook_url', label: 'Webhook URL', secret: true }] },
  { key: 'generic_webhook', label: '通用 Webhook', values: {}, fields: [{ key: 'webhook_url', label: 'Webhook URL', secret: true }] },
]

/** 全量平台清单（含已停用，恢复用）。 */
const platformCatalog = [
  { id: 'toutiao', name: '今日头条' }, { id: 'baidu', name: '百度热搜' }, { id: 'weibo', name: '微博' },
  { id: 'zhihu', name: '知乎' }, { id: 'douyin', name: '抖音' }, { id: 'bilibili-hot-search', name: 'B站热搜' },
  { id: 'thepaper', name: '澎湃新闻' }, { id: 'ifeng', name: '凤凰网' }, { id: 'tieba', name: '贴吧' },
  { id: 'cls-hot', name: '财联社热门' }, { id: 'wallstreetcn-hot', name: '华尔街见闻' },
]

const rssFeeds = computed(() => (cfg.value?.rss?.feeds ?? []))
const allPlatforms = computed(() => {
  const enabled = new Set((cfg.value?.platforms?.sources ?? []).map((s) => s.id))
  return platformCatalog.map((p) => ({ ...p, on: enabled.has(p.id) }))
})
const enabledPlatforms = computed(() => allPlatforms.value.filter((p) => p.on))
const regions = reactive({})
const regionRows = [
  { key: 'hotlist', label: '热榜', desc: '关键词匹配 / AI 筛选结果', color: 'text-blue-600' },
  { key: 'rss', label: 'RSS 订阅', desc: '订阅源文章与词频统计', color: 'text-emerald-600' },
  { key: 'ai_analysis', label: 'AI 分析', desc: '五板块深度分析', color: 'text-violet-600' },
  { key: 'new_items', label: '新增热点', desc: '本次新上榜 / 新文章', color: 'text-slate-400' },
  { key: 'standalone', label: '独立展示区', desc: '指定平台完整榜单（不受筛选影响）', color: 'text-amber-600' },
]
const nextRunText = computed(() => {
  if (!schedule.next_run) return ''
  const d = new Date(schedule.next_run)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

/** 深度取值。 @param {object} obj @param {string} path */
const getPath = (obj, path) => path.split('.').reduce((o, k) => (o == null ? o : o[k]), obj)
/** 深度赋值。 @param {object} obj @param {string} path @param {any} val */
const setPath = (obj, path, val) => {
  const keys = path.split('.')
  const last = keys.pop()
  let cur = obj
  for (const k of keys) {
    if (typeof cur[k] !== 'object' || cur[k] === null) cur[k] = {}
    cur = cur[k]
  }
  cur[last] = val
}

/** 平台启停（增删 sources 数组）。 @param {object} p */
const togglePlatform = (p) => {
  const sources = cfg.value.platforms.sources
  const idx = sources.findIndex((s) => s.id === p.id)
  if (p.on && idx >= 0) sources.splice(idx, 1)
  else if (!p.on && idx < 0) sources.push({ id: p.id, name: p.name })
}

/** 新增空白 RSS 源。 */
const addFeed = () => {
  cfg.value.rss.feeds.push({ id: `custom-${Date.now()}`, name: '', url: '', enabled: true })
}

/** 保存全部配置为新版本。 */
const save = async () => {
  saving.value = true
  isError.value = false
  message.value = ''
  try {
    for (const r of regionRows) cfg.value.display.regions[r.key] = regions[r.key]
    cfg.value.ai.fallback_models = fallbackText.value
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
    for (const ch of channelForms) {
      const target = cfg.value.notification.channels[ch.key]
      for (const [k, v] of Object.entries(ch.values)) {
        if (v !== undefined && v !== '') target[k] = v
      }
    }
    const comment = `界面保存：${tab.value}（${new Date().toLocaleString('zh-CN', { hour12: false })}）`
    await api('/api/v1/config', { method: 'PUT', body: JSON.stringify({ config: cfg.value, files: { ...files }, comment }) })
    savedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    message.value = '已保存为新版本，下一任务生效'
    await loadVersions()
  } catch (e) {
    isError.value = true
    message.value = e.message
  } finally {
    saving.value = false
  }
}

/** 用界面当前草稿测试 AI 连通性（无需先保存）。 */
const testingAi = ref(false)
const aiTestResult = ref('')
const aiTestOk = ref(false)
const testAi = async () => {
  testingAi.value = true
  aiTestResult.value = ''
  try {
    const result = await api('/api/v1/config/test-ai', {
      method: 'POST',
      body: JSON.stringify({
        model: cfg.value?.ai?.model || '',
        api_key: cfg.value?.ai?.api_key || '',
        api_base: cfg.value?.ai?.api_base || '',
      }),
    })
    aiTestOk.value = true
    aiTestResult.value = `连接正常 · ${result.model} · ${result.latency_ms}ms`
  } catch (e) {
    aiTestOk.value = false
    aiTestResult.value = e.message
  } finally {
    testingAi.value = false
  }
}

/** 保存调度（独立于配置版本）。 */
const saveSchedule = async () => {
  isError.value = false
  try {
    const result = await api('/api/v1/config/schedule', {
      method: 'PUT',
      body: JSON.stringify({ cron_expr: schedule.cron_expr, enabled: schedule.enabled }),
    })
    Object.assign(schedule, result)
    message.value = `调度已更新：${result.cron}`
  } catch (e) {
    isError.value = true
    message.value = e.message
  }
}

/** 加载版本 diff（与前一版本对比）。 @param {object} v */
const selectedVersion = ref(null)
const diffData = ref(null)
const loadDiff = async (v) => {
  selectedVersion.value = v
  diffData.value = null
  try {
    diffData.value = await api(`/api/v1/config/versions/${v.id}/diff`)
  } catch (e) {
    isError.value = true
    message.value = e.message
  }
}

/** 回滚到指定版本。 @param {object} v */
const rollback = async (v) => {
  isError.value = false
  try {
    await api(`/api/v1/config/versions/${v.id}/rollback`, { method: 'POST' })
    message.value = `已回滚到 v${v.version}，正在重新加载配置`
    await Promise.all([loadConfig(), loadVersions()])
  } catch (e) {
    isError.value = true
    message.value = e.message
  }
}

/** ISO 时间转本地串。 @param {string} iso */
const fmtDate = (iso) => new Date(iso).toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })

const loadVersions = async () => {
  versions.value = await api('/api/v1/config/versions')
}

/** 加载当前配置与调度，构建编辑草稿。 */
const loadConfig = async () => {
  const data = await api('/api/v1/config')
  cfg.value = data.config
  cfg.value.platforms = cfg.value.platforms || { enabled: true, sources: [] }
  cfg.value.rss = cfg.value.rss || { enabled: true, feeds: [] }
  cfg.value.report = cfg.value.report || {}
  cfg.value.filter = cfg.value.filter || { method: 'keyword' }
  cfg.value.display = cfg.value.display || { regions: {} }
  cfg.value.ai = cfg.value.ai || {}
  cfg.value.notification = cfg.value.notification || { channels: {} }
  cfg.value.notification.channels = cfg.value.notification.channels || {}
  cfg.value.ai.temperature = cfg.value.ai.temperature ?? 1.0
  cfg.value.ai.max_tokens = cfg.value.ai.max_tokens ?? 5000
  cfg.value.ai.timeout = cfg.value.ai.timeout ?? 120
  cfg.value.ai.num_retries = cfg.value.ai.num_retries ?? 1
  fallbackText.value = (cfg.value.ai.fallback_models || []).join(', ')
  providerId.value = providers.find((p) => cfg.value.ai.model?.startsWith(p.prefix))?.id || 'custom'
  Object.assign(files, data.files || {})
  for (const r of regionRows) {
    regions[r.key] = Boolean(cfg.value.display.regions?.[r.key] ?? true)
  }
  for (const ch of channelForms) {
    const source = cfg.value.notification.channels[ch.key] || {}
    for (const f of ch.fields) ch.values[f.key] = source[f.key] ?? ''
  }
}

onMounted(async () => {
  await Promise.all([loadConfig(), loadVersions()])
  try {
    Object.assign(schedule, await api('/api/v1/config/schedule'))
  } catch {
    /* 调度读取失败不阻塞页面 */
  }
})
</script>
