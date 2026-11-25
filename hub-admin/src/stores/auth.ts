import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const apiKey = ref<string>(localStorage.getItem('hub_admin_api_key') || 'dev-admin-key')
  const username = ref<string>(localStorage.getItem('hub_admin_user') || 'admin')

  function setApiKey(key: string, user: string = 'admin') {
    apiKey.value = key
    username.value = user
    localStorage.setItem('hub_admin_api_key', key)
    localStorage.setItem('hub_admin_user', user)
  }

  function logout() {
    apiKey.value = ''
    username.value = ''
    localStorage.removeItem('hub_admin_api_key')
    localStorage.removeItem('hub_admin_user')
  }

  return {
    apiKey,
    username,
    setApiKey,
    logout,
  }
})
