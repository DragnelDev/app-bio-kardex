<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { http } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import EstadoLote from '@/components/EstadoLote.vue'
import Modal from '@/components/Modal.vue'
import ProductoPicker from '@/components/ProductoPicker.vue'
import { mensajeError } from '@/utils/errores'
import { base, fecha } from '@/utils/format'
import type { Paginado, Presentacion, Producto, StockItem } from '@/types'

const auth = useAuthStore()
const puedeCorregir = computed(() => auth.puede(['regente']))

const pestana = ref<'stock' | 'alertas' | 'ingreso'>('stock')
const sucursal = computed(() => auth.sucursalActivaId)

const pestanas = computed(() => [
  { id: 'stock' as const, texto: 'Stock por lote' },
  { id: 'alertas' as const, texto: `Alertas (${vencidos.value.length + porVencer.value.length})` },
  { id: 'ingreso' as const, texto: 'Ingreso de mercaderia' },
])

// ---- stock
const filas = ref<StockItem[]>([])
const total = ref(0)
const pagina = ref(1)
const q = ref('')
const estado = ref('')
const conStock = ref(true)
const error = ref('')

let temporizador: ReturnType<typeof setTimeout> | undefined
watch([q, estado, conStock], () => {
  clearTimeout(temporizador)
  temporizador = setTimeout(() => cargarStock(1), 300)
})

async function cargarStock(p = 1) {
  if (!sucursal.value) return
  pagina.value = p
  error.value = ''
  try {
    const { data } = await http.get<Paginado<StockItem>>('/inventario/stock/', {
      params: {
        sucursal: sucursal.value,
        q: q.value || undefined,
        estado: estado.value || undefined,
        con_stock: conStock.value ? 1 : 0,
        page: p,
      },
    })
    filas.value = data.results
    total.value = data.count
  } catch (e) {
    error.value = mensajeError(e)
  }
}

// ---- alertas
const vencidos = ref<StockItem[]>([])
const porVencer = ref<StockItem[]>([])
const diasAlerta = ref(90)

async function cargarAlertas() {
  if (!sucursal.value) return
  const { data } = await http.get<{
    dias_alerta: number
    vencidos: StockItem[]
    por_vencer: StockItem[]
  }>('/inventario/alertas/', { params: { sucursal: sucursal.value } })
  vencidos.value = data.vencidos
  porVencer.value = data.por_vencer
  diasAlerta.value = data.dias_alerta
}

// ---- acciones sobre un lote (baja / ajuste / bloqueo)
const lote = ref<StockItem | null>(null)
const accion = ref<'baja' | 'ajuste'>('baja')
const cantidad = ref(0)
const motivo = ref('')
const errorAccion = ref('')

function abrirAccion(item: StockItem, tipo: 'baja' | 'ajuste') {
  lote.value = item
  accion.value = tipo
  cantidad.value = tipo === 'baja' ? item.cantidad : item.cantidad
  motivo.value = tipo === 'baja' && item.estado === 'vencido' ? 'Producto vencido' : ''
  errorAccion.value = ''
}

async function ejecutarAccion() {
  if (!lote.value) return
  errorAccion.value = ''
  try {
    if (accion.value === 'baja') {
      await http.post('/inventario/bajas/', {
        sucursal: sucursal.value,
        lote: lote.value.lote_id,
        cantidad: cantidad.value,
        motivo: motivo.value,
      })
    } else {
      await http.post('/inventario/ajustes/', {
        sucursal: sucursal.value,
        lote: lote.value.lote_id,
        cantidad_real: cantidad.value,
        motivo: motivo.value,
      })
    }
    lote.value = null
    await refrescar()
  } catch (e) {
    errorAccion.value = mensajeError(e)
  }
}

async function alternarBloqueo(item: StockItem) {
  try {
    await http.post('/inventario/bloqueos/', {
      sucursal: sucursal.value,
      lote: item.lote_id,
      bloqueado: !item.bloqueado,
    })
    await refrescar()
  } catch (e) {
    error.value = mensajeError(e)
  }
}

async function refrescar() {
  await Promise.all([cargarStock(pagina.value), cargarAlertas()])
}

// ---- ingreso de mercaderia
const producto = ref<Producto | null>(null)
const picker = ref<InstanceType<typeof ProductoPicker> | null>(null)
const ingreso = reactive({
  presentacion: null as number | null,
  cantidad: 1,
  numero_lote: '',
  fecha_vencimiento: '',
  costo_total: '',
})
const errorIngreso = ref('')
const okIngreso = ref('')
const guardandoIngreso = ref(false)

const presentacionElegida = computed<Presentacion | undefined>(() =>
  producto.value?.presentaciones.find((x) => x.id === ingreso.presentacion),
)
const equivalencia = computed(() =>
  presentacionElegida.value && producto.value
    ? `${ingreso.cantidad * presentacionElegida.value.factor} ${producto.value.unidad_base}`
    : '',
)

function alElegirProducto(p: Producto | null) {
  producto.value = p
  const activas = p?.presentaciones.filter((x) => x.activa) ?? []
  ingreso.presentacion = (activas.find((x) => x.nivel === 'caja') ?? activas[0])?.id ?? null
}

async function registrarIngreso() {
  errorIngreso.value = ''
  okIngreso.value = ''
  guardandoIngreso.value = true
  try {
    await http.post('/inventario/ingresos/', {
      sucursal: sucursal.value,
      presentacion: ingreso.presentacion,
      cantidad: ingreso.cantidad,
      numero_lote: ingreso.numero_lote,
      fecha_vencimiento: ingreso.fecha_vencimiento,
      costo_total: ingreso.costo_total === '' ? undefined : Number(ingreso.costo_total).toFixed(2),
    })
    okIngreso.value = `Ingresado: ${equivalencia.value} (lote ${ingreso.numero_lote}).`
    ingreso.numero_lote = ''
    ingreso.cantidad = 1
    ingreso.costo_total = ''
    await refrescar()
  } catch (e) {
    errorIngreso.value = mensajeError(e)
  } finally {
    guardandoIngreso.value = false
  }
}

onMounted(refrescar)
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold">Inventario</h1>

    <div class="flex gap-1 border-b border-slate-200 dark:border-slate-700" role="tablist">
      <button
        v-for="t in pestanas"
        :key="t.id"
        role="tab"
        :aria-selected="pestana === t.id"
        class="-mb-px border-b-2 px-3 py-2 text-sm"
        :class="
          pestana === t.id
            ? 'border-brand-500 font-medium text-brand-700 dark:text-brand-400'
            : 'border-transparent text-slate-500'
        "
        @click="pestana = t.id"
      >
        {{ t.texto }}
      </button>
    </div>

    <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>

    <!-- Stock -->
    <template v-if="pestana === 'stock'">
      <div class="flex flex-wrap items-center gap-3">
        <input
          v-model="q"
          class="input !w-64"
          type="search"
          placeholder="Producto, principio activo o lote"
        />
        <select v-model="estado" class="input !w-40">
          <option value="">Todos los estados</option>
          <option value="ok">OK</option>
          <option value="por_vencer">Por vencer</option>
          <option value="vencido">Vencidos</option>
          <option value="bloqueado">Bloqueados</option>
        </select>
        <label class="flex items-center gap-2 text-sm"
          ><input v-model="conStock" type="checkbox" /> Solo con stock</label
        >
      </div>
      <div class="card overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr>
              <th class="th">Producto</th>
              <th class="th">Lote</th>
              <th class="th">Vence</th>
              <th class="th text-right">Stock (u. base)</th>
              <th class="th">Estado</th>
              <th class="th"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="s in filas"
              :key="s.id"
              class="border-t border-slate-200 dark:border-slate-700"
            >
              <td class="td">{{ s.producto }}</td>
              <td class="td">{{ s.numero_lote }}</td>
              <td class="td">
                {{ fecha(s.fecha_vencimiento) }}
                <span class="text-xs text-slate-500">({{ s.dias_para_vencer }} d)</span>
              </td>
              <td class="td text-right font-medium">{{ s.cantidad }}</td>
              <td class="td"><EstadoLote :estado="s.estado" /></td>
              <td v-if="puedeCorregir" class="td space-x-1 whitespace-nowrap text-right">
                <button class="btn-ghost !px-2 !py-1 text-xs" @click="abrirAccion(s, 'ajuste')">
                  Ajustar
                </button>
                <button class="btn-ghost !px-2 !py-1 text-xs" @click="alternarBloqueo(s)">
                  {{ s.bloqueado ? 'Desbloquear' : 'Bloquear' }}
                </button>
                <button class="btn-ghost !px-2 !py-1 text-xs" @click="abrirAccion(s, 'baja')">
                  Baja
                </button>
              </td>
              <td v-else class="td"></td>
            </tr>
            <tr v-if="!filas.length">
              <td class="td text-slate-500" colspan="6">Sin resultados.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="total > 50" class="flex items-center justify-between text-sm">
        <button class="btn-ghost" :disabled="pagina <= 1" @click="cargarStock(pagina - 1)">
          Anterior
        </button>
        <span>Pagina {{ pagina }} · {{ total }} lotes</span>
        <button class="btn-ghost" :disabled="pagina * 50 >= total" @click="cargarStock(pagina + 1)">
          Siguiente
        </button>
      </div>
    </template>

    <!-- Alertas -->
    <template v-else-if="pestana === 'alertas'">
      <div class="card overflow-x-auto">
        <h2 class="p-4 pb-0 font-semibold text-danger">
          Vencidos con stock ({{ vencidos.length }})
        </h2>
        <p class="px-4 text-xs text-slate-500">No se pueden vender. Registra su baja.</p>
        <table class="w-full">
          <tbody>
            <tr
              v-for="s in vencidos"
              :key="s.id"
              class="border-t border-slate-200 dark:border-slate-700"
            >
              <td class="td">{{ s.producto }}</td>
              <td class="td">{{ s.numero_lote }}</td>
              <td class="td">{{ fecha(s.fecha_vencimiento) }}</td>
              <td class="td text-right">{{ s.cantidad }}</td>
              <td v-if="puedeCorregir" class="td text-right">
                <button class="btn-danger !px-2 !py-1 text-xs" @click="abrirAccion(s, 'baja')">
                  Dar de baja
                </button>
              </td>
            </tr>
            <tr v-if="!vencidos.length">
              <td class="td text-slate-500">Ninguno.</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card overflow-x-auto">
        <h2 class="p-4 pb-0 font-semibold text-warn">
          Vencen en los proximos {{ diasAlerta }} dias ({{ porVencer.length }})
        </h2>
        <table class="w-full">
          <tbody>
            <tr
              v-for="s in porVencer"
              :key="s.id"
              class="border-t border-slate-200 dark:border-slate-700"
            >
              <td class="td">{{ s.producto }}</td>
              <td class="td">{{ s.numero_lote }}</td>
              <td class="td">
                {{ fecha(s.fecha_vencimiento) }}
                <span class="text-xs text-slate-500">({{ s.dias_para_vencer }} d)</span>
              </td>
              <td class="td text-right">{{ base(s.cantidad) }}</td>
            </tr>
            <tr v-if="!porVencer.length">
              <td class="td text-slate-500">Ninguno.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Ingreso -->
    <form v-else class="card max-w-2xl space-y-3 p-4" @submit.prevent="registrarIngreso">
      <p class="text-sm text-slate-500">
        El lote y la fecha de vencimiento son obligatorios. Se ingresa a la sucursal activa.
      </p>
      <label class="block text-sm"
        ><span class="mb-1 block font-medium">Producto</span
        ><ProductoPicker ref="picker" @elegir="alElegirProducto"
      /></label>
      <div v-if="producto" class="grid gap-3 sm:grid-cols-2">
        <label class="text-sm">
          <span class="mb-1 block font-medium">Presentacion</span>
          <select v-model="ingreso.presentacion" class="input" required>
            <option
              v-for="x in producto.presentaciones.filter((y) => y.activa)"
              :key="x.id"
              :value="x.id"
            >
              {{ x.nombre || x.nivel_display }} (x{{ x.factor }})
            </option>
          </select>
        </label>
        <label class="text-sm">
          <span class="mb-1 block font-medium">Cantidad</span>
          <input v-model.number="ingreso.cantidad" class="input" type="number" min="1" required />
          <span class="text-xs text-slate-500">= {{ equivalencia }}</span>
        </label>
        <label class="text-sm"
          ><span class="mb-1 block font-medium">N° de lote *</span
          ><input v-model="ingreso.numero_lote" class="input" required maxlength="60"
        /></label>
        <label class="text-sm"
          ><span class="mb-1 block font-medium">Vencimiento *</span
          ><input v-model="ingreso.fecha_vencimiento" class="input" type="date" required
        /></label>
        <label class="text-sm"
          ><span class="mb-1 block font-medium">Costo total (Bs, opcional)</span
          ><input v-model="ingreso.costo_total" class="input" type="number" min="0" step="0.01"
        /></label>
      </div>
      <p v-if="errorIngreso" class="text-sm text-danger" role="alert">{{ errorIngreso }}</p>
      <p v-if="okIngreso" class="text-sm text-brand-600" role="status">{{ okIngreso }}</p>
      <button type="submit" class="btn-primary" :disabled="!producto || guardandoIngreso">
        Registrar ingreso
      </button>
    </form>

    <Modal
      v-if="lote"
      :titulo="accion === 'baja' ? 'Dar de baja' : 'Ajustar stock'"
      @cerrar="lote = null"
    >
      <form class="space-y-3" @submit.prevent="ejecutarAccion">
        <p class="text-sm">
          {{ lote.producto }} · lote {{ lote.numero_lote }} · stock actual {{ lote.cantidad }}
        </p>
        <label class="block text-sm">
          <span class="mb-1 block font-medium">{{
            accion === 'baja'
              ? 'Cantidad a dar de baja (u. base)'
              : 'Cantidad real contada (u. base)'
          }}</span>
          <input
            v-model.number="cantidad"
            class="input"
            type="number"
            :min="accion === 'baja' ? 1 : 0"
            required
          />
        </label>
        <label class="block text-sm"
          ><span class="mb-1 block font-medium">Motivo *</span
          ><input v-model="motivo" class="input" required maxlength="255"
        /></label>
        <p v-if="errorAccion" class="text-sm text-danger" role="alert">{{ errorAccion }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn-ghost" @click="lote = null">Cancelar</button>
          <button type="submit" :class="accion === 'baja' ? 'btn-danger' : 'btn-primary'">
            Confirmar
          </button>
        </div>
      </form>
    </Modal>
  </section>
</template>
