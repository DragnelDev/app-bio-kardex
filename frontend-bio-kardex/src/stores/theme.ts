import { ref } from 'vue'
import { defineStore } from 'pinia'

const KEY = 'bk-theme'

function leer(): 'light' | 'dark' | null {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'light' || v === 'dark' ? v : null
  } catch {
    return null
  }
}

export const useThemeStore = defineStore('theme', () => {
  const isDark = ref(false)

  function aplicar() {
    document.documentElement.classList.toggle('dark', isDark.value)
  }

  function init() {
    const guardado = leer()
    isDark.value = guardado
      ? guardado === 'dark'
      : window.matchMedia('(prefers-color-scheme: dark)').matches
    aplicar()
  }

  function toggle() {
    isDark.value = !isDark.value
    aplicar()
    try {
      localStorage.setItem(KEY, isDark.value ? 'dark' : 'light')
    } catch {
      /* sin almacenamiento: el tema vive solo en memoria */
    }
  }

  return { isDark, init, toggle }
})
