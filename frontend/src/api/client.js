/**
 * API 客户端：统一携带 JWT、解析 JSON 与错误。
 * 401 时清除会话并跳转登录页（由路由守卫完成重定向）。
 */

const BASE = ''

/**
 * 发起带鉴权的 fetch 请求。
 * @param {string} path - API 路径（如 /api/v1/jobs）
 * @param {object} [options] - fetch 选项，可覆盖 method/body/headers
 * @returns {Promise<any>} 解析后的 JSON
 * @throws {Error} 网络/HTTP 错误（message 携带后端 detail）
 */
export async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  const token = localStorage.getItem('tr_token')
  if (token) headers.Authorization = `Bearer ${token}`

  const resp = await fetch(BASE + path, { ...options, headers })
  if (resp.status === 401) {
    localStorage.removeItem('tr_token')
    localStorage.removeItem('tr_user')
    if (!location.hash.includes('/login')) location.hash = '#/login'
    throw new Error('登录已过期')
  }
  const text = await resp.text()
  const data = text ? JSON.parse(text) : null
  if (!resp.ok) {
    throw new Error(extractErrorMessage(data, resp.status))
  }
  return data
}

/** Pydantic 校验错误类型的中文映射。 */
const VALIDATION_MESSAGES = {
  string_too_short: '不能为空',
  string_too_long: '超长',
  missing: '缺少必填字段',
  value_error: '格式不正确',
}

/**
 * 从后端错误响应提取可读消息。
 * FastAPI 的 detail 可能是字符串（HTTPException）或数组（422 校验错误）。
 * @param {any} data - 响应 JSON
 * @param {number} status - HTTP 状态码
 * @returns {string} 人类可读错误消息
 */
function extractErrorMessage(data, status) {
  const detail = data && data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = (item.loc || []).slice(1).join('.') || '字段'
        const zh = VALIDATION_MESSAGES[item.type] || item.msg || '不合法'
        return `${field}${zh}`
      })
      .join('；')
  }
  if (detail && typeof detail === 'object') return detail.msg || JSON.stringify(detail)
  return `请求失败（${status}）`
}
