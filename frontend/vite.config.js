import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// 开发代理指向本地 webapp（默认 8080，可用 env 覆盖）
const target = process.env.WEBAPP_URL || 'http://127.0.0.1:8080'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target, ws: true },
      '/reports': target,
    },
  },
})
