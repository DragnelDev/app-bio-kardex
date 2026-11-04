<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { http } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import Modal from '@/components/Modal.vue'
import TicketVenta from '@/components/TicketVenta.vue'
import { mensajeError } from '@/utils/errores'
import { bs, fechaHora, hoyISO } from '@/utils/format'
import type { Paginado, Venta, VentaResumen } from '@/types'

const auth = useAuthStore()
const esSupervisor = computed(() => auth.puede(['regente']))

const filtros = reactive({ desde: hoyISO(), hasta: hoyISO(), numero: '', estado: '' })
const ventas = ref<VentaResumen[]>([])
const total = ref(0)
const pagina = ref(1)
const cargando = ref(false)
const error = ref('')

const detalle = ref<Venta | null>(null)
const modo = ref<'ver' | 'anular' | 'devolver'>('ver')
const motivo = ref('')
const metodoReembolso = ref<'efectivo' | 'qr'>('efectivo')
const aDevolver = reactive<Record<number, number>>({})
const accionError = ref('')
const ocupado = ref(false)

async function cargar(p = 1) {
  if (!auth.sucursalActivaId) return
  cargando.value = true
  error.value = ''
  pagina.value = p
  try {
    const { data } = await http.get<Paginado<VentaResumen>>('/ventas/', {
      params: {
        sucursal: auth.sucursalActivaId,
        desde: filtros.desde || undefined,
        hasta: filtros.hasta || undefined,
        numero: filtros.numero || undefined,
        estado: filtros.estado || undefined,
        page: p,
        page_size: 25,
      },
    })
    ventas.value = data.results
    total.value = data.count
  } catch (e) {
    error.value = mensajeError(e)
  } finally {
    cargando.value = false
  }
}

async function ver(id: number) {
  const { data } = await http.get<Venta>(`/ventas/${id}/`)
  detalle.value = data
  modo.value = 'ver'
  motivo.value = ''
  accionError.value = ''
  for (const k of Object.keys(aDevolver)) delete aDevolver[Number(k)]
}

async function anular() {
  if (!detalle.value) return
  ocupado.value = true
  accionError.value = ''
  try {
    const { data } = await http.post<Venta>(`/ventas/${detalle.value.id}/anular/`, {
      motivo: motivo.value,
    })
    detalle.value = data
    modo.value = 'ver'
    await cargar(pagina.value)
  } catch (e) {
    accionError.value = mensajeError(e)
  } finally {
    ocupado.value = false
  }
}

async function devolver() {
  if (!detalle.value) return
  const items = Object.entries(aDevolver)
    .filter(([, c]) => c > 0)
    .map(([id, c]) => ({ venta_item_lote: Number(id), cantidad: c }))
  if (!items.length) {
    accionError.value = 'Indica la cantidad a devolver de al menos un lote.'
    return
  }
  ocupado.value = true
  accionError.value = ''
  try {
    await http.post(`/ventas/${detalle.value.id}/devolucion/`, {
      items,
      motivo: motivo.value,
      metodo_reembolso: metodoReembolso.value,
    })
    await ver(detalle.value.id)
  } catch (e) {
    accionError.value = mensajeError(e)
  } finally {
    ocupado.value = false
  }
}

function imprimir() {
  window.print()
}

onMounted(() => cargar())
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold">Ventas</h1>

    <form class="card flex flex-wrap items-end gap-3 p-3" @submit.prevent="cargar(1)">
      <label class="text-sm"
        ><span class="mb-1 block">Desde</span
        ><input v-model="filtros.desde" type="date" class="input"
      /></label>
      <label class="text-sm"
        ><span class="mb-1 block">Hasta</span
        ><input v-model="filtros.hasta" type="date" class="input"
      /></label>
      <label class="text-sm"
        ><span class="mb-1 block">N°</span
        ><input v-model="filtros.numero" type="number" min="1" class="input !w-24"
      /></label>
      <label class="text-sm">
        <span class="mb-1 block">Estado</span>
        <select v-model="filtros.estado" class="input">
          <option value="">Todos</option>
          <option value="completada">Completadas</option>
          <option value="anulada">Anuladas</option>
        </select>
      </label>
      <button type="submit" class="btn-primary">Filtrar</button>
    </form>

    <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>

    <div class="card overflow-x-auto">
      <table class="w-full">
        <thead>
          <tr>
            <th class="th">N°</th>
            <th class="th">Fecha</th>
            <th class="th">Cliente</th>
            <th class="th">Cajero</th>
            <th class="th text-right">Total</th>
            <th class="th">Estado</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="v in ventas"
            :key="v.id"
            class="cursor-pointer border-t border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700/40"
            @click="ver(v.id)"
          >
            <td class="td">{{ v.numero }}</td>
            <td class="td">{{ fechaHora(v.creado_en) }}</td>
            <td class="td">{{ v.nombre_cliente }}</td>
            <td class="td">{{ v.cajero_nombre }}</td>
            <td class="td text-right">{{ bs(v.total) }}</td>
            <td class="td">
              <span :class="v.estado === 'anulada' ? 'text-danger' : 'text-brand-600'">{{
                v.estado
              }}</span>
            </td>
          </tr>
          <tr v-if="!ventas.length && !cargando">
            <td class="td text-slate-500" colspan="6">Sin ventas en el rango.</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="total > 25" class="flex items-center justify-between text-sm">
      <button class="btn-ghost" :disabled="pagina <= 1" @click="cargar(pagina - 1)">
        Anterior
      </button>
      <span>Pagina {{ pagina }} · {{ total }} ventas</span>
      <button class="btn-ghost" :disabled="pagina * 25 >= total" @click="cargar(pagina + 1)">
        Siguiente
      </button>
    </div>

    <Modal
      v-if="detalle"
      :titulo="`Venta N° ${detalle.numero}`"
      ancho="max-w-xl"
      @cerrar="detalle = null"
    >
      <template v-if="modo === 'ver'">
        <TicketVenta :venta="detalle" />
        <p v-if="detalle.estado === 'anulada'" class="mt-2 text-sm text-danger">
          Motivo: {{ detalle.motivo_anulacion }}
        </p>
        <div class="mt-4 flex flex-wrap justify-end gap-2 print:hidden">
          <button type="button" class="btn-ghost" @click="imprimir">
            <i class="pi pi-print" aria-hidden="true"></i> Imprimir
          </button>
          <template v-if="esSupervisor && detalle.estado === 'completada'">
            <button type="button" class="btn-ghost" @click="modo = 'devolver'">Devolucion</button>
            <button type="button" class="btn-danger" @click="modo = 'anular'">Anular</button>
          </template>
        </div>
      </template>

      <form v-else-if="modo === 'anular'" class="space-y-3" @submit.prevent="anular">
        <p class="text-sm">
          Se devolvera todo el stock a sus lotes. Solo es posible mientras el turno siga abierto.
        </p>
        <label class="block text-sm"
          ><span class="mb-1 block font-medium">Motivo</span
          ><input v-model="motivo" class="input" required maxlength="255"
        /></label>
        <p v-if="accionError" class="text-sm text-danger" role="alert">{{ accionError }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn-ghost" @click="modo = 'ver'">Volver</button>
          <button type="submit" class="btn-danger" :disabled="ocupado">Anular venta</button>
        </div>
      </form>

      <form v-else class="space-y-3" @submit.prevent="devolver">
        <p class="text-sm">
          Indica cuantas unidades base devuelve el cliente de cada lote vendido.
        </p>
        <div
          v-for="i in detalle.items"
          :key="i.id"
          class="rounded-lg border border-slate-200 p-2 text-sm dark:border-slate-700"
        >
          <p class="font-medium">
            {{ i.producto_nombre }}
            <span class="font-normal text-slate-500"
              >({{ i.cantidad }} x {{ i.presentacion_nombre }})</span
            >
          </p>
          <label
            v-for="l in i.lotes"
            :key="l.id"
            class="mt-1 flex items-center justify-between gap-2"
          >
            <span
              >Lote {{ l.numero_lote }} · vendidas {{ l.cantidad_base
              }}<span v-if="l.devuelta"> · ya devueltas {{ l.devuelta }}</span></span
            >
            <input
              v-model.number="aDevolver[l.id]"
              class="input !w-20 !py-0.5 text-right"
              type="number"
              min="0"
              :max="l.cantidad_base - l.devuelta"
            />
          </label>
        </div>
        <label class="block text-sm"
          ><span class="mb-1 block font-medium">Motivo</span
          ><input v-model="motivo" class="input" required maxlength="255"
        /></label>
        <label class="block text-sm">
          <span class="mb-1 block font-medium">Reembolso por</span>
          <select v-model="metodoReembolso" class="input">
            <option value="efectivo">Efectivo</option>
            <option value="qr">QR / Transferencia</option>
          </select>
        </label>
        <p v-if="accionError" class="text-sm text-danger" role="alert">{{ accionError }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn-ghost" @click="modo = 'ver'">Volver</button>
          <button type="submit" class="btn-primary" :disabled="ocupado">
            Registrar devolucion
          </button>
        </div>
      </form>
    </Modal>
  </section>
</template>
