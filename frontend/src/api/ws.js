/**
 * 状态 WebSocket 客户端：任务状态与日志流实时推送。
 * 断线自动重连（指数退避封顶 8s）；onEvent 回调分发服务端事件。
 */

/**
 * 创建实时状态连接。
 * @param {(event: {type: string, [key: string]: any}) => void} onEvent - 事件回调
 * @returns {{close: () => void, alive: () => boolean}} 控制句柄
 */
export function createStatusSocket(onEvent) {
  let ws = null
  let closed = false
  let retryDelay = 0
  let alive = false

  const connect = () => {
    if (closed) return
    const token = localStorage.getItem('tr_token') || ''
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${location.host}/api/v1/ws/status?token=${encodeURIComponent(token)}`)
    ws.onopen = () => {
      alive = true
      retryDelay = 0
    }
    ws.onmessage = (event) => {
      try {
        onEvent(JSON.parse(event.data))
      } catch {
        /* 非 JSON 消息忽略 */
      }
    }
    ws.onclose = () => {
      alive = false
      if (!closed) {
        retryDelay = Math.min(retryDelay * 2 || 1000, 8000)
        setTimeout(connect, retryDelay)
      }
    }
    ws.onerror = () => ws.close()
  }

  connect()
  return {
    close: () => {
      closed = true
      if (ws) ws.close()
    },
    alive: () => alive,
  }
}
