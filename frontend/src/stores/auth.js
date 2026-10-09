import { defineStore } from 'pinia'
import { api } from '../api/client'

/** 认证状态：token 持久化于 localStorage，启动时恢复。 */
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('tr_token') || '',
    username: localStorage.getItem('tr_user') || '',
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
  },
  actions: {
    /**
     * 登录并持久化令牌。
     * @param {string} username
     * @param {string} password
     */
    async login(username, password) {
      const data = await api('/api/v1/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      this.token = data.access_token
      this.username = data.username
      localStorage.setItem('tr_token', this.token)
      localStorage.setItem('tr_user', data.username)
    },
    /** 退出登录。 */
    logout() {
      this.token = ''
      this.username = ''
      localStorage.removeItem('tr_token')
      localStorage.removeItem('tr_user')
    },
  },
})
