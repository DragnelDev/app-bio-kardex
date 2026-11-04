<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { http } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import EstadoLote from '@/components/EstadoLote.vue'
import Modal from '@/components/Modal.vue'
import { mensajeError } from '@/utils/errores'
import { fecha, fechaHora } from '@/utils/format'
import type { Paginado, StockItem, Traspaso } from '@/types'

const auth = useAuthStore()
const sucursal = computed(() => auth.sucursalActivaId)

const traspasos = ref<Traspaso[]>([])
const estado = ref('')
const error = ref('')

async function cargar() {
  if (!sucursal.value) return
  try {
    const { data } = await http.get<Paginado<Traspaso>>('/inventario/traspasos/', {
      params: { sucursal: sucursal.value, estado: estado.value || undefined },
    })
    traspasos.value = data.results
  } catch (e) {
    error.value = mensajeError(e)
  }
}
watch(estado, cargar)

// ---- nuevo traspaso
const nuevo = ref(false)
const destinos = ref<{ id: number; nombre: string }[]>([])
const destino = ref<number | null>(null)
const observacion = ref('')
const busqueda = ref('')
const encontrados = ref<StockItem[]>([])
const items = ref<{ stock: StockItem; cantidad: number }[]>([])
const errorNuevo = ref('')
const enviando = ref(false)

async function abrirNuevo() {
  nuevo.value = true
  errorNuevo.value = ''
  items.value = []
  encontrados.value = []
  busqueda.value = ''
  observacion.value = ''
  const { data } = await http.get<{ id: number; nombre: string }[]>('/sucursales/destinos/')
  destinos.value = data.filter((d) => d.id !== sucursal.value)
  destino.value = destinos.value[0]?.id ?? null
}

let temporizador: ReturnType<typeof setTimeout> | undefined
watch(busqueda, (valor) => {
  clearTimeout(temporizador)
  if (valor.trim().length < 2) {
    encontrados.value = []
    return
  }
  temporizador = setTimeout(async () => {
    const { data } = await http.get<Paginado<StockItem>>('/inventario/stock/', {
      params: { sucursal: sucursal.value, q: valor.trim(), con_stock: 1 },
    })
    encontrados.value = data.results.filter((s) => s.estado === 'ok' || s.estado === 'por_vencer')
  }, 250)
})

function agregar(s: StockItem) {
  if (items.value.some((i) => i.stock.lote_id === s.lote_id)) return
  items.value.push({ stock: s, cantidad: 1 })
}

async function enviar() {
  errorNuevo.value = ''
  enviando.value = true
  try {
    await http.post('/inventario/traspasos/', {
      origen: sucursal.value,
      destino: destino.value,
      observacion: observacion.value,
      items: items.value.map((i) => ({ lote: i.stock.lote_id, cantidad: i.cantidad })),
    })
    nuevo.value = false
    await cargar()
  } catch (e) {
    errorNuevo.value = mensajeError(e)
  } finally {
    enviando.value = false
  }
}

// ---- recepcion / rechazo
const recibiendo = ref<Traspaso | null>(null)
const recibidos = ref<Record<number, number>>({})
const obsRecepcion = ref('')
const modoRechazo = ref(false)
const errorRecepcion = ref('')

function abrirRecepcion(t: Traspaso, rechazo: boolean) {
  recibiendo.value = t
  modoRechazo.value = rechazo
  obsRecepcion.value = ''
  errorRecepcion.value = ''
  recibidos.value = Object.fromEntries(t.items.map((i) => [i.id, i.cantidad_enviada]))
}

async function resolver() {
  if (!recibiendo.value) return
  errorRecepcion.value = ''
  try {
    if (modoRechazo.value) {
      await http.post(`/inventario/traspasos/${recibiendo.value.id}/rechazar/`, {
        observacion: obsRecepcion.value,
      })
    } else {
      await http.post(`/inventario/traspasos/${recibiendo.value.id}/recibir/`, {
        items: Object.entries(recibidos.value).map(([item, cantidad]) => ({
          item: Number(item),
          cantidad,
        })),
        observacion: obsRecepcion.value,
      })
    }
    recibiendo.value = null
    await cargar()
  } catch (e) {
    errorRecepcion.value = mensajeError(e)
  }
}

const etiquetaEstado: Record<Traspaso['estado'], string> = {
  enviado: 'En transito',
  recibido: 'Recibido',
  rechazado: 'Rechazado',
}

onMounted(cargar)
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-center gap-3">
      <h1 class="text-2xl font-semibold">Traspasos</h1>
      <select v-model="estado" class="input !w-40">
        <option value="">Todos</option>
        <option value="enviado">En transito</option>
        <option value="recibido">Recibidos</option>
        <option value="rechazado">Rechazados</option>
      </select>
      <button type="button" class="btn-primary ml-auto" @click="abrirNuevo">
        <i class="pi pi-send" aria-hidden="true"></i> Nuevo traspaso
      </button>
    </div>
    <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>

    <div class="space-y-3">
      <article v-for="t in traspasos" :key="t.id" class="card p-4">
        <div class="flex flex-wrap items-center justify-between gap-2">
          <h2 class="font-semibold">
            #{{ t.id }} · {{ t.origen_nombre }} → {{ t.destino_nombre }}
          </h2>
          <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs dark:bg-slate-700">{{
            etiquetaEstado[t.estado]
          }}</span>
        </div>
        <p class="text-xs text-slate-500">
          {{ fechaHora(t.creado_en) }} · {{ t.creado_por_nombre
          }}<span v-if="t.observacion"> · {{ t.observacion }}</span>
        </p>
        <ul class="mt-2 text-sm">
          <li
            v-for="i in t.items"
            :key="i.id"
            class="flex justify-between border-t border-slate-100 py-1 dark:border-slate-700"
          >
            <span
              >{{ i.producto }} · lote {{ i.numero_lote }} (vence
              {{ fecha(i.fecha_vencimiento) }})</span
            >
            <span>
              {{ i.cantidad_enviada }}
              <span
                v-if="i.cantidad_recibida !== null"
                :class="i.diferencia ? 'text-danger' : 'text-slate-500'"
              >
                → recibidas {{ i.cantidad_recibida }}
              </span>
            </span>
          </li>
        </ul>
        <p v-if="t.observacion_recepcion" class="mt-1 text-xs text-slate-500">
          Recepcion: {{ t.observacion_recepcion }}
        </p>
        <div
          v-if="t.estado === 'enviado' && t.destino === sucursal"
          class="mt-3 flex justify-end gap-2"
        >
          <button type="button" class="btn-ghost" @click="abrirRecepcion(t, true)">Rechazar</button>
          <button type="button" class="btn-primary" @click="abrirRecepcion(t, false)">
            Recibir
          </button>
        </div>
      </article>
      <p v-if="!traspasos.length" class="text-sm text-slate-500">Sin traspasos.</p>
    </div>

    <Modal v-if="nuevo" titulo="Nuevo traspaso" ancho="max-w-2xl" @cerrar="nuevo = false">
      <form class="space-y-3" @submit.prevent="enviar">
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="text-sm"
            ><span class="mb-1 block font-medium">Destino</span>
            <select v-model="destino" class="input" required>
              <option v-for="d in destinos" :key="d.id" :value="d.id">{{ d.nombre }}</option>
            </select>
          </label>
          <label class="text-sm"
            ><span class="mb-1 block font-medium">Observacion</span
            ><input v-model="observacion" class="input" maxlength="255"
          /></label>
        </div>
        <label class="block text-sm"
          ><span class="mb-1 block font-medium">Buscar lote en esta sucursal</span
          ><input
            v-model="busqueda"
            class="input"
            type="search"
            placeholder="Producto o numero de lote"
        /></label>
        <ul v-if="encontrados.length" class="card max-h-40 overflow-y-auto text-sm">
          <li v-for="s in encontrados" :key="s.id">
            <button
              type="button"
              class="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left hover:bg-slate-100 dark:hover:bg-slate-700"
              @click="agregar(s)"
            >
              <span
                >{{ s.producto }} · lote {{ s.numero_lote }} · vence
                {{ fecha(s.fecha_vencimiento) }}</span
              >
              <span class="flex items-center gap-2"
                >{{ s.cantidad }} u. <EstadoLote :estado="s.estado"
              /></span>
            </button>
          </li>
        </ul>
        <div
          v-for="i in items"
          :key="i.stock.lote_id"
          class="flex items-center justify-between gap-2 rounded-lg border border-slate-200 p-2 text-sm dark:border-slate-700"
        >
          <span>{{ i.stock.producto }} · lote {{ i.stock.numero_lote }}</span>
          <span class="flex items-center gap-2">
            <input
              v-model.number="i.cantidad"
              class="input !w-24 !py-0.5 text-right"
              type="number"
              min="1"
              :max="i.stock.cantidad"
            />
            <span class="text-xs text-slate-500">de {{ i.stock.cantidad }}</span>
            <button
              type="button"
              class="text-slate-400 hover:text-danger"
              aria-label="Quitar"
              @click="items = items.filter((x) => x !== i)"
            >
              <i class="pi pi-trash" aria-hidden="true"></i>
            </button>
          </span>
        </div>
        <p v-if="errorNuevo" class="text-sm text-danger" role="alert">{{ errorNuevo }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn-ghost" @click="nuevo = false">Cancelar</button>
          <button
            type="submit"
            class="btn-primary"
            :disabled="!items.length || !destino || enviando"
          >
            Enviar traspaso
          </button>
        </div>
      </form>
    </Modal>

    <Modal
      v-if="recibiendo"
      :titulo="
        modoRechazo ? `Rechazar traspaso #${recibiendo.id}` : `Recibir traspaso #${recibiendo.id}`
      "
      @cerrar="recibiendo = null"
    >
      <form class="space-y-3" @submit.prevent="resolver">
        <template v-if="!modoRechazo">
          <p class="text-sm text-slate-500">
            Confirma lo que llego. Si hay diferencias, indica una observacion.
          </p>
          <div
            v-for="i in recibiendo.items"
            :key="i.id"
            class="flex items-center justify-between gap-2 text-sm"
          >
            <span
              >{{ i.producto }} · lote {{ i.numero_lote }} (enviadas {{ i.cantidad_enviada }})</span
            >
            <input
              v-model.number="recibidos[i.id]"
              class="input !w-24 !py-0.5 text-right"
              type="number"
              min="0"
              :max="i.cantidad_enviada"
            />
          </div>
        </template>
        <p v-else class="text-sm text-slate-500">
          Todo el stock volvera a los mismos lotes del origen.
        </p>
        <label class="block text-sm"
          ><span class="mb-1 block font-medium"
            >Observacion{{ modoRechazo ? ' (motivo) *' : '' }}</span
          ><input v-model="obsRecepcion" class="input" maxlength="255" :required="modoRechazo"
        /></label>
        <p v-if="errorRecepcion" class="text-sm text-danger" role="alert">{{ errorRecepcion }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn-ghost" @click="recibiendo = null">Cancelar</button>
          <button type="submit" :class="modoRechazo ? 'btn-danger' : 'btn-primary'">
            {{ modoRechazo ? 'Rechazar' : 'Confirmar recepcion' }}
          </button>
        </div>
      </form>
    </Modal>
  </section>
</template>
