# TrendRadar 管理平台部署指南

> 平台架构与设计依据：`docs/plan/platform.html`（规划）、`docs/design/trendradar-platform.pen`（UI 设计，13 屏）

## 一、Docker 快速部署（推荐）

```bash
cd docker

# 1. 按需修改 .env 中"管理平台"段的 WEB_* 变量
#    （生产务必设置 WEB_SECRET_KEY，如：openssl rand -hex 32）

# 2. 构建并启动（web + mcp 双容器）
docker compose -f docker-compose-web.yml --env-file .env up -d --build

# 3. 访问
open http://127.0.0.1:8080
# 默认账号 admin / trendradar（WEB_ADMIN_PASSWORD）
```

**镜像说明**（`docker/Dockerfile.web`，多阶段构建）：

- 阶段 1：`node:20-alpine` 构建 `frontend/`（Vue 3 + Vite + Tailwind）产物
- 阶段 2：`python:3.12-slim` 安装引擎 + 平台 + 前端产物，**非 root 运行**，含健康检查
- 容器内置调度器（APScheduler），**无需 supercronic**

**卷与端口**：

| 项 | 值 | 说明 |
|---|---|---|
| 端口 | `127.0.0.1:8080`（`WEB_PORT` 可改） | 默认仅本机可访问，公网请走反代 + HTTPS |
| `../config` | rw | 平台保存配置后投影器**双写**共享卷，MCP/CLI 零改造读到最新 |
| `../output` | rw | 引擎数据日库与 HTML 报告（与 mcp 容器共享） |
| `web-data` 卷 | 私有 | platform.db（用户/配置版本/任务记录）+ 任务投影与日志 |

**⚠️ 与原部署互斥**：本文件用平台内置调度取代 `trendradar`（supercronic）容器。请勿同时启用原 `docker-compose.yml` 的爬虫容器与 `docker-compose-web.yml`，否则双调度器并发写同一日库。二者选一：

- 只要推送、不要管理界面 → 用原 `docker-compose.yml`
- 要平台化管理 → 用 `docker-compose-web.yml`

## 二、本地开发运行

```bash
# 后端（引擎依赖 + 平台依赖）
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-web.txt -e .
.venv/bin/python -m uvicorn webapp.main:app --port 8080

# 前端（开发代理已指向 8080）
cd frontend && npm install && npm run dev     # http://localhost:5173
```

首次启动自动完成初始化（幂等）：创建 `admin` 用户、从 `config/config.yaml` 导入配置 v1（含词表/提示词等 8 个配套文件）、按 `WEB_CRON` 建立调度。

## 三、已实现能力（对应路线图 M1-M4，全部落地）

| 能力 | 说明 |
|---|---|
| 登录鉴权 | JWT（24h 可配），登录限速，PBKDF2 密码哈希，中文错误提示 |
| 运行监控 | 任务历史 / 状态徽章 / 错误摘要 / **WebSocket 实时日志流（LIVE）**，断线自动降级轮询 |
| 渠道送达 | 引擎输出结构化结果 → `job_channel_results` 落库 → 任务表「送达 n/n」列 |
| 手动触发 | 与 cron 同一互斥路径，冲突返回 409 |
| 内置调度 | `*/30` 起步 cron，`/api/v1/config/schedule` 可读写热生效 |
| 配置管理 | 五 tab：数据源（平台开关/RSS 增删改）/ 调度（频率+cron）/ 筛选与展示（双模式/词表/兴趣编辑器）/ **AI 与通知（6 提供商预设·模型联想·全参数·备用模型链·测试连接·9 渠道凭据）**/ 版本历史（**diff 对比**+回滚） |
| 配置版本化 | DB 真相源、掩码自动合并还原、版本 diff、回滚（指针迁移）、审计日志 |
| 配置投影 | `run/{v}/config/` 快照 + `output→共享卷` 符号链接 + 双写共享卷（MCP/CLI 同源） |
| 报告中心 | 扫描 `output/html` 索引 + iframe 在线预览 + 静态托管 |
| 数据浏览 | 热榜查询（日期/平台/关键词/分页）+ **趋势分析**（关键词热度矩阵/平台对比/源健康热力/**关键词共现与异动信号——复用 MCP AnalyticsTools 同源口径**） |
| 仪表盘 | 今日任务/成功率/数据用量/下次运行 + 热榜速览，15s 自动刷新 |

## 三点五、MCP API Key 鉴权

平台为 MCP HTTP 端点（3333）提供 API Key 保护：

- **Key 生成**：平台首次启动自动生成，存于共享卷 `config/mcp_auth.json`（MCP 容器只读挂载即可校验）；也可用 `MCP_API_KEY` 环境变量覆盖（优先级更高）。两者皆无时不启用鉴权（兼容模式）。
- **客户端接入**：系统设置 →「MCP Server 接入」→ 选 HTTP 模式 → **复制 JSON**（已自动携带 `headers.Authorization`），粘贴到 Cursor / Cline 等客户端即可。
- **Key 轮换**：同一页面「重新生成」→ 写入审计 → **重启 MCP 容器**加载新 Key。
- stdio（本地运行）模式不启用鉴权（本机信任环境）。

## 三点六、接入 OpenAI 兼容模型（GLM / 硅基流动 / vLLM 等）

配置管理 → AI 与通知 → 提供商选「OpenAI 兼容端点」：

| 提供商 | 模型示例 | API Base |
|---|---|---|
| 智谱 GLM | `openai/glm-4.6`、`openai/glm-4-flash` | `https://open.bigmodel.cn/api/paas/v4` |
| 硅基流动 | `openai/deepseek-ai/DeepSeek-V3` | `https://api.siliconflow.cn/v1` |
| Moonshot | `openai/moonshot-v1-8k` | `https://api.moonshot.cn/v1` |
| 本地 vLLM/OllamaOpenAI | `openai/<模型名>` | `http://localhost:8000/v1` |

填写后点「测试连接」（**界面草稿直测，无需先保存**），通过后「保存为新版本」。

## 四、关键 API

```
POST /api/v1/auth/login                      登录
GET  /api/v1/config                          当前配置（脱敏）
PUT  /api/v1/config                          保存新版本
GET  /api/v1/config/versions                 版本列表
POST /api/v1/config/versions/{id}/rollback   回滚
GET|PUT /api/v1/config/schedule              调度读写
GET  /api/v1/jobs?limit=&status=             任务历史
POST /api/v1/jobs/trigger                    手动触发
GET  /api/v1/jobs/{id}/logs?offset=          日志增量
GET  /api/v1/data/news?date=&q=&platform=    热榜查询
GET  /api/v1/reports                         报告索引
GET  /api/v1/system/status                   系统状态
```

## 五、引擎侧适配点（全部零侵入设计）

- `trendradar/__main__.py`：`_should_open_browser()` 增加 `TRENDRADAR_HEADLESS=1` 判断（子进程模式不弹浏览器）
- 配置注入：子进程通过 `CONFIG_PATH` / `FREQUENCY_WORDS_PATH` 环境变量使用投影快照
- 存储落位：投影器注入绝对 `data_dir` + `output` 符号链接，数据/报告天然落共享卷
- CLI 模式完全不受影响：`python -m trendradar` 行为与改造前一致

## 六、状态说明

规划 M1-M4 全部落地，含复盘补丁（配置双写闭环、投影敏感信息权限、双调度器互斥防护）。
analytics 同源通过 Web 直连 `mcp_server.tools.analytics.AnalyticsTools` 实现（零重构，
MCP 27 工具未动）。后续可选增强：MCP HTTP 服务并入 web 容器（`/mcp` 挂载）、多用户开放。
