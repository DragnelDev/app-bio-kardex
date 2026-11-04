<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { http } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import ProductoPicker from '@/components/ProductoPicker.vue'
import { mensajeError } from '@/utils/errores'
import { fechaHora } from '@/utils/format'
import type { Movimiento, Paginado, Producto } from '@/types'

const auth = useAuthStore()

const TIPOS = [
  ['ingreso', 'Ingreso'],
  ['venta', 'Venta'],
  ['devolucion_venta', 'Devolucion de venta'],
  ['anulacion_venta', 'Anulacion de venta'],
  ['baja', 'Baja'],
  ['ajuste', 'Ajuste'],
  ['traspaso_salida', 'Traspaso (salida)'],
  ['traspaso_entrada', 'Traspaso (entrada)'],
  ['traspaso_rechazo', 'Traspaso rechazado'],
] as const

const filtros = reactive({ tipo: '', desde: '', hasta: '' })
const producto = ref<Producto | null>(null)
const movimientos = ref<Movimiento[]>([])
const total = ref(0)
const pagina = ref(1)
const error = ref('')

const sucursal = computed(() => auth.sucursalActivaId)

async function cargar(p = 1) {
  if (!sucursal.value) return
  pagina.value = p
  error.value = ''
  try {
    const { data } = await http.get<Paginado<Movimiento>>('/inventario/kardex/', {
      params: {
        sucursal: sucursal.value,
        producto: producto.value?.id,
        tipo: filtros.tipo || undefined,
        desde: filtros.desde || undefined,
        hasta: filtros.hasta || undefined,
        page: p,
      },
    })
    movimientos.value = data.results
    total.value = data.count
  } catch (e) {
    error.value = mensajeError(e)
  }
}

function alElegir(p: Producto | null) {
  producto.value = p
  cargar(1)
}

onMounted(() => cargar())
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold">Kardex</h1>
    <p class="text-sm text-slate-500">
      Registro inalterable de todos los movimientos de stock. Las correcciones se hacen con
      movimientos compensatorios.
    </p>

    <form class="card flex flex-wrap items-end gap-3 p-3" @submit.prevent="cargar(1)">
      <label class="w-64 text-sm"
        ><span class="mb-1 block">Producto</span
        ><ProductoPicker placeholder="Todos" @elegir="alElegir"
      /></label>
      <label class="text-sm">
        <span class="mb-1 block">Tipo</span>
        <select v-model="filtros.tipo" class="input">
          <option value="">Todos</option>
          <option v-for="t in TIPOS" :key="t[0]" :value="t[0]">{{ t[1] }}</option>
        </select>
      </label>
      <label class="text-sm"
        ><span class="mb-1 block">Desde</span
        ><input v-model="filtros.desde" type="date" class="input"
      /></label>
      <label class="text-sm"
        ><span class="mb-1 block">Hasta</span
        ><input v-model="filtros.hasta" type="date" class="input"
      /></label>
      <button type="submit" class="btn-primary">Filtrar</button>
    </form>

    <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>

    <div class="card overflow-x-auto">
      <table class="w-full">
        <thead>
          <tr>
            <th class="th">Fecha</th>
            <th class="th">Producto</th>
            <th class="th">Lote</th>
            <th class="th">Tipo</th>
            <th class="th text-right">Cantidad</th>
            <th class="th text-right">Saldo</th>
            <th class="th">Usuario</th>
            <th class="th">Detalle</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="m in movimientos"
            :key="m.id"
            class="border-t border-slate-200 dark:border-slate-700"
          >
            <td class="td whitespace-nowrap">{{ fechaHora(m.creado_en) }}</td>
            <td class="td">{{ m.producto }}</td>
            <td class="td">{{ m.numero_lote }}</td>
            <td class="td">{{ m.tipo_display }}</td>
            <td
              class="td text-right font-medium"
              :class="m.cantidad < 0 ? 'text-danger' : 'text-brand-600'"
            >
              {{ m.cantidad > 0 ? '+' : '' }}{{ m.cantidad }}
            </td>
            <td class="td text-right">{{ m.saldo }}</td>
            <td class="td">{{ m.usuario_nombre }}</td>
            <td class="td text-xs text-slate-500">{{ m.motivo }}</td>
          </tr>
          <tr v-if="!movimientos.length">
            <td class="td text-slate-500" colspan="8">Sin movimientos.</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="total > 50" class="flex items-center justify-between text-sm">
      <button class="btn-ghost" :disabled="pagina <= 1" @click="cargar(pagina - 1)">
        Anterior
      </button>
      <span>Pagina {{ pagina }} · {{ total }} movimientos</span>
      <button class="btn-ghost" :disabled="pagina * 50 >= total" @click="cargar(pagina + 1)">
        Siguiente
      </button>
    </div>
  </section>
</template>
