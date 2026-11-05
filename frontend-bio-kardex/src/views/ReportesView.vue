<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { http } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { mensajeError } from '@/utils/errores'
import { bs, fecha, hoyISO } from '@/utils/format'

interface ReporteVentas {
  resumen: {
    ventas: number
    total: string
    iva: string
    descuentos: string
    anuladas: number
    devoluciones: string
    ticket_promedio: string
  }
  por_metodo: { metodo: string; total: string }[]
  por_dia: { dia: string; cantidad: number; total: string }[]
  por_cajero: { cajero: string; cantidad: number; total: string }[]
  top_productos: { producto: string; unidades_base: number; total: string }[]
}
interface ReporteValorizado {
  total: string
  lotes_sin_costo: number
  productos: { producto: string; cantidad: number; valor: string }[]
}
interface RegistroControlado {
  fecha: string
  venta: number
  producto: string
  lote: string
  cantidad_base: number
  receta: string
  medico: string
  documento: string
  cliente: string
  cajero: string
}

const auth = useAuthStore()
const pestana = ref<'ventas' | 'valorizado' | 'controlados'>('ventas')
const filtros = reactive({ desde: hoyISO(), hasta: hoyISO() })
const error = ref('')
const cargando = ref(false)

const ventas = ref<ReporteVentas | null>(null)
const valorizado = ref<ReporteValorizado | null>(null)
const controlados = ref<RegistroControlado[]>([])

const pestanas = [
  { id: 'ventas' as const, texto: 'Ventas' },
  { id: 'valorizado' as const, texto: 'Stock valorizado' },
  { id: 'controlados' as const, texto: 'Libro de controlados' },
]

const usaRango = computed(() => pestana.value !== 'valorizado')
const maxDia = computed(() => Math.max(1, ...(ventas.value?.por_dia.map((d) => Number(d.total)) ?? [1])))

function parametros(extra: Record<string, string> = {}) {
  return {
    sucursal: auth.sucursalActivaId,
    desde: usaRango.value ? filtros.desde : undefined,
    hasta: usaRango.value ? filtros.hasta : undefined,
    ...extra,
  }
}

async function cargar() {
  if (!auth.sucursalActivaId) return
  cargando.value = true
  error.value = ''
  try {
    if (pestana.value === 'ventas') {
      ventas.value = (await http.get<ReporteVentas>('/reportes/ventas/', { params: parametros() })).data
    } else if (pestana.value === 'valorizado') {
      valorizado.value = (await http.get<ReporteValorizado>('/reportes/valorizado/', { params: parametros() })).data
    } else {
      controlados.value = (
        await http.get<{ registros: RegistroControlado[] }>('/reportes/controlados/', { params: parametros() })
      ).data.registros
    }
  } catch (e) {
    error.value = mensajeError(e)
  } finally {
    cargando.value = false
  }
}

function cambiar(id: typeof pestana.value) {
  pestana.value = id
  cargar()
}

async function descargarCsv() {
  error.value = ''
  try {
    const { data } = await http.get<Blob>(`/reportes/${pestana.value}/`, {
      params: parametros({ formato: 'csv' }),
      responseType: 'blob',
    })
    const url = URL.createObjectURL(data)
    const enlace = document.createElement('a')
    enlace.href = url
    enlace.download = `${pestana.value}_${filtros.desde}_${filtros.hasta}.csv`
    enlace.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = mensajeError(e)
  }
}

onMounted(cargar)
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold">Reportes</h1>

    <div class="flex gap-1 border-b border-slate-200 dark:border-slate-700" role="tablist">
      <button
        v-for="t in pestanas"
        :key="t.id"
        role="tab"
        :aria-selected="pestana === t.id"
        class="-mb-px border-b-2 px-3 py-2 text-sm"
        :class="pestana === t.id ? 'border-brand-500 font-medium text-brand-700 dark:text-brand-400' : 'border-transparent text-slate-500'"
        @click="cambiar(t.id)"
      >
        {{ t.texto }}
      </button>
    </div>

    <form class="card flex flex-wrap items-end gap-3 p-3" @submit.prevent="cargar">
      <template v-if="usaRango">
        <label class="text-sm"><span class="mb-1 block">Desde</span><input v-model="filtros.desde" type="date" class="input" /></label>
        <label class="text-sm"><span class="mb-1 block">Hasta</span><input v-model="filtros.hasta" type="date" class="input" /></label>
      </template>
      <button type="submit" class="btn-primary">Generar</button>
      <button type="button" class="btn-ghost" @click="descargarCsv"><i class="pi pi-download" aria-hidden="true"></i> Descargar CSV</button>
    </form>

    <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>
    <p v-if="cargando" class="text-slate-500">Generando...</p>

    <!-- Ventas -->
    <template v-if="pestana === 'ventas' && ventas">
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div class="card p-4"><p class="text-sm text-slate-500">Ventas</p><p class="text-2xl font-semibold">{{ ventas.resumen.ventas }}</p></div>
        <div class="card p-4"><p class="text-sm text-slate-500">Total vendido</p><p class="text-2xl font-semibold text-brand-600 dark:text-brand-400">{{ bs(ventas.resumen.total) }}</p></div>
        <div class="card p-4"><p class="text-sm text-slate-500">IVA incluido</p><p class="text-2xl font-semibold">{{ bs(ventas.resumen.iva) }}</p></div>
        <div class="card p-4"><p class="text-sm text-slate-500">Ticket promedio</p><p class="text-2xl font-semibold">{{ bs(ventas.resumen.ticket_promedio) }}</p></div>
        <div class="card p-4"><p class="text-sm text-slate-500">Descuentos</p><p class="text-lg font-semibold">{{ bs(ventas.resumen.descuentos) }}</p></div>
        <div class="card p-4"><p class="text-sm text-slate-500">Devoluciones</p><p class="text-lg font-semibold">{{ bs(ventas.resumen.devoluciones) }}</p></div>
        <div class="card p-4"><p class="text-sm text-slate-500">Anuladas</p><p class="text-lg font-semibold">{{ ventas.resumen.anuladas }}</p></div>
      </div>

      <div class="grid gap-4 lg:grid-cols-2">
        <div class="card p-4">
          <h2 class="mb-2 font-semibold">Por dia</h2>
          <ul class="space-y-1 text-sm">
            <li v-for="d in ventas.por_dia" :key="d.dia">
              <div class="flex justify-between"><span>{{ fecha(d.dia) }} · {{ d.cantidad }} ventas</span><span>{{ bs(d.total) }}</span></div>
              <div class="h-1.5 rounded bg-slate-100 dark:bg-slate-700"><div class="h-1.5 rounded bg-brand-500" :style="{ width: `${(Number(d.total) / maxDia) * 100}%` }"></div></div>
            </li>
            <li v-if="!ventas.por_dia.length" class="text-slate-500">Sin ventas en el rango.</li>
          </ul>
        </div>
        <div class="space-y-4">
          <div class="card p-4">
            <h2 class="mb-2 font-semibold">Por metodo de pago</h2>
            <p v-for="m in ventas.por_metodo" :key="m.metodo" class="flex justify-between text-sm"><span>{{ m.metodo === 'qr' ? 'QR / Transferencia' : 'Efectivo' }}</span><span>{{ bs(m.total) }}</span></p>
          </div>
          <div class="card p-4">
            <h2 class="mb-2 font-semibold">Por cajero</h2>
            <p v-for="c in ventas.por_cajero" :key="c.cajero" class="flex justify-between text-sm"><span>{{ c.cajero }} · {{ c.cantidad }}</span><span>{{ bs(c.total) }}</span></p>
          </div>
        </div>
      </div>

      <div class="card overflow-x-auto">
        <h2 class="p-4 pb-0 font-semibold">Productos mas vendidos</h2>
        <table class="w-full">
          <thead><tr><th class="th">Producto</th><th class="th text-right">Unidades base</th><th class="th text-right">Total</th></tr></thead>
          <tbody>
            <tr v-for="t in ventas.top_productos" :key="t.producto" class="border-t border-slate-200 dark:border-slate-700">
              <td class="td">{{ t.producto }}</td><td class="td text-right">{{ t.unidades_base }}</td><td class="td text-right">{{ bs(t.total) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Valorizado -->
    <template v-else-if="pestana === 'valorizado' && valorizado">
      <div class="card p-4">
        <p class="text-sm text-slate-500">Valor total del inventario a costo</p>
        <p class="text-3xl font-semibold text-brand-600 dark:text-brand-400">{{ bs(valorizado.total) }}</p>
        <p v-if="valorizado.lotes_sin_costo" class="mt-1 text-sm text-warn">
          {{ valorizado.lotes_sin_costo }} lote(s) sin costo registrado no estan valorizados.
        </p>
      </div>
      <div class="card overflow-x-auto">
        <table class="w-full">
          <thead><tr><th class="th">Producto</th><th class="th text-right">Unidades base</th><th class="th text-right">Valor a costo</th></tr></thead>
          <tbody>
            <tr v-for="p in valorizado.productos" :key="p.producto" class="border-t border-slate-200 dark:border-slate-700">
              <td class="td">{{ p.producto }}</td><td class="td text-right">{{ p.cantidad }}</td><td class="td text-right">{{ bs(p.valor) }}</td>
            </tr>
            <tr v-if="!valorizado.productos.length"><td class="td text-slate-500" colspan="3">Sin stock.</td></tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Libro de controlados -->
    <div v-else-if="pestana === 'controlados'" class="card overflow-x-auto">
      <table class="w-full">
        <thead>
          <tr><th class="th">Fecha</th><th class="th">Venta</th><th class="th">Producto</th><th class="th">Lote</th><th class="th text-right">Cant.</th><th class="th">Receta</th><th class="th">Medico</th><th class="th">Cliente</th></tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in controlados" :key="i" class="border-t border-slate-200 dark:border-slate-700">
            <td class="td whitespace-nowrap">{{ r.fecha }}</td><td class="td">{{ r.venta }}</td><td class="td">{{ r.producto }}</td>
            <td class="td">{{ r.lote }}</td><td class="td text-right">{{ r.cantidad_base }}</td><td class="td">{{ r.receta }}</td>
            <td class="td">{{ r.medico }}</td><td class="td">{{ r.cliente }} ({{ r.documento }})</td>
          </tr>
          <tr v-if="!controlados.length"><td class="td text-slate-500" colspan="8">Sin ventas de controlados en el rango.</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
