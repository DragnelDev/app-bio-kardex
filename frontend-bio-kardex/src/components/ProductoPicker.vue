<script setup lang="ts">
import { ref, watch } from 'vue'
import { http } from '@/api/http'
import type { Paginado, Producto } from '@/types'

defineProps<{ placeholder?: string }>()
const emit = defineEmits<{ elegir: [producto: Producto | null] }>()

const texto = ref('')
const resultados = ref<Producto[]>([])
const abierto = ref(false)
const elegido = ref<Producto | null>(null)
let temporizador: ReturnType<typeof setTimeout> | undefined

watch(texto, (valor) => {
  clearTimeout(temporizador)
  if (elegido.value && valor === etiqueta(elegido.value)) return
  if (elegido.value) {
    elegido.value = null
    emit('elegir', null)
  }
  if (valor.trim().length < 2) {
    resultados.value = []
    return
  }
  temporizador = setTimeout(async () => {
    const { data } = await http.get<Paginado<Producto>>('/productos/', {
      params: { q: valor.trim(), activo: 1, page_size: 8 },
    })
    resultados.value = data.results
    abierto.value = true
  }, 250)
})

function etiqueta(p: Producto) {
  return `${p.nombre_comercial} ${p.concentracion}`.trim()
}

function elegir(p: Producto) {
  elegido.value = p
  texto.value = etiqueta(p)
  abierto.value = false
  emit('elegir', p)
}

function cerrarLuego() {
  setTimeout(() => (abierto.value = false), 150)
}

function limpiar() {
  texto.value = ''
  elegido.value = null
  resultados.value = []
  emit('elegir', null)
}

defineExpose({ limpiar })
</script>

<template>
  <div class="relative">
    <input
      v-model="texto"
      class="input"
      type="search"
      autocomplete="off"
      :placeholder="placeholder ?? 'Buscar producto...'"
      @focus="abierto = resultados.length > 0"
      @blur="cerrarLuego"
    />
    <ul
      v-if="abierto && resultados.length"
      class="card absolute z-20 mt-1 max-h-64 w-full overflow-y-auto py-1"
    >
      <li v-for="p in resultados" :key="p.id">
        <button
          type="button"
          class="block w-full px-3 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700"
          @mousedown.prevent="elegir(p)"
        >
          <span class="font-medium">{{ p.nombre_comercial }}</span>
          <span class="text-slate-500">
            {{ p.concentracion }} · {{ p.principio_activo_nombre }}</span
          >
        </button>
      </li>
    </ul>
  </div>
</template>
