<script setup lang="ts">
import { computed } from 'vue'
import type { EstadoLote } from '@/types'

const props = defineProps<{ estado: EstadoLote }>()

const info = computed(() => {
  switch (props.estado) {
    case 'vencido':
      return { texto: 'Vencido', clase: 'bg-danger/15 text-danger' }
    case 'bloqueado':
      return { texto: 'Bloqueado', clase: 'bg-danger/15 text-danger' }
    case 'por_vencer':
      return { texto: 'Por vencer', clase: 'bg-warn/20 text-amber-700 dark:text-warn' }
    default:
      return { texto: 'OK', clase: 'bg-brand-500/15 text-brand-700 dark:text-brand-400' }
  }
})
</script>

<template>
  <span class="inline-block rounded-full px-2 py-0.5 text-xs font-medium" :class="info.clase">
    {{ info.texto }}
  </span>
</template>
