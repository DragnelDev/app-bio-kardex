<script setup lang="ts">
import { useThemeStore } from '@/stores/theme'

const theme = useThemeStore()
</script>

<template>
  <button
    type="button"
    class="flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 transition hover:bg-slate-100 focus-visible:outline-2 focus-visible:outline-brand-500 dark:text-slate-300 dark:hover:bg-slate-700"
    :aria-label="theme.isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'"
    :aria-pressed="theme.isDark"
    @click="theme.toggle()"
  >
    <i :class="['pi', theme.isDark ? 'pi-sun' : 'pi-moon']" aria-hidden="true"></i>
  </button>
</template>
