<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'

const props = defineProps<{ titulo: string; ancho?: string }>()
const emit = defineEmits<{ cerrar: [] }>()

function tecla(e: KeyboardEvent) {
  if (e.key === 'Escape') emit('cerrar')
}
onMounted(() => window.addEventListener('keydown', tecla))
onBeforeUnmount(() => window.removeEventListener('keydown', tecla))
</script>

<template>
  <div
    class="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4"
    @mousedown.self="emit('cerrar')"
  >
    <div
      class="card mt-8 w-full p-5"
      :class="props.ancho ?? 'max-w-lg'"
      role="dialog"
      aria-modal="true"
      :aria-label="props.titulo"
    >
      <div class="mb-4 flex items-center justify-between">
        <h2 class="text-lg font-semibold">{{ props.titulo }}</h2>
        <button
          type="button"
          class="btn-ghost !px-2 !py-1"
          aria-label="Cerrar"
          @click="emit('cerrar')"
        >
          <i class="pi pi-times" aria-hidden="true"></i>
        </button>
      </div>
      <slot />
    </div>
  </div>
</template>
