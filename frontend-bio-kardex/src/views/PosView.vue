<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { http } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { usePosStore } from '@/stores/pos'
import Modal from '@/components/Modal.vue'
import TicketVenta from '@/components/TicketVenta.vue'
import { mensajeError } from '@/utils/errores'
import { base, bs, fecha, redondear } from '@/utils/format'
import type { PosProducto, Turno, Venta } from '@/types'

const auth = useAuthStore()
const pos = usePosStore()

const q = ref('')
const resultados = ref<PosProducto[]>([])
const buscando = ref(false)
const turno = ref<Turno | null>(null)
const cargandoTurno = ref(true)
const inputBusqueda = ref<HTMLInputElement | null>(null)

const cobrando = ref(false)
const qrMonto = ref(0)
const efectivoRecibido = ref(0)
const qrReferencia = ref('')
const comprobante = ref<File | null>(null)
const enviando = ref(false)
const error = ref('')
const aviso = ref('')
const ticket = ref<Venta | null>(null)

const puedeDescontar = computed(() => auth.puede(['regente']))
const aplicadoEfectivo = computed(() => redondear(pos.total - qrMonto.value))
const vuelto = computed(() =>
  aplicadoEfectivo.value > 0 ? redondear(efectivoRecibido.value - aplicadoEfectivo.value) : 0,
)
const puedeCobrar = computed(
  () => turno.value !== null && pos.lineas.length > 0 && pos.total > 0 && !pos.hayExcesoDeStock,
)

let temporizador: ReturnType<typeof setTimeout> | undefined

async function buscar() {
  const texto = q.value.trim()
  if (texto.length < 2 || !auth.sucursalActivaId) {
    resultados.value = []
    return
  }
  buscando.value = true
  try {
    const { data } = await http.get<PosProducto[]>('/pos/buscar/', {
      params: { sucursal: auth.sucursalActivaId, q: texto },
    })
    // descarta respuestas viejas si el usuario ya cambio la busqueda
    if (texto === q.value.trim()) resultados.value = data
  } catch (e) {
    error.value = mensajeError(e)
  } finally {
    buscando.value = false
  }
}

watch(q, () => {
  clearTimeout(temporizador)
  temporizador = setTimeout(buscar, 250)
})

/** Enter: si el texto es un codigo de barras exacto, agrega esa presentacion directo. */
async function alEnter() {
  clearTimeout(temporizador)
  await buscar()
  const codigo = q.value.trim()
  for (const prod of resultados.value) {
    const pres = prod.presentaciones.find((x) => x.codigo_barras === codigo)
    if (pres && pres.disponible > 0) {
      pos.agregar(prod, pres)
      q.value = ''
      resultados.value = []
      return
    }
  }
}

async function cargarTurno() {
  if (!auth.sucursalActivaId) return
  try {
    const { data } = await http.get<{ turno: Turno | null }>('/turnos/actual/', {
      params: { sucursal: auth.sucursalActivaId },
    })
    turno.value = data.turno
  } finally {
    cargandoTurno.value = false
  }
}

function abrirCobro() {
  if (!puedeCobrar.value) return
  error.value = ''
  qrMonto.value = 0
  efectivoRecibido.value = pos.total
  qrReferencia.value = ''
  comprobante.value = null
  cobrando.value = true
}

watch(qrMonto, () => {
  if (efectivoRecibido.value < aplicadoEfectivo.value)
    efectivoRecibido.value = aplicadoEfectivo.value
})

function alElegirArchivo(e: Event) {
  comprobante.value = (e.target as HTMLInputElement).files?.[0] ?? null
}

async function confirmarVenta() {
  error.value = ''
  if (qrMonto.value < 0 || qrMonto.value > pos.total) {
    error.value = 'El monto QR debe estar entre 0 y el total.'
    return
  }
  if (aplicadoEfectivo.value > 0 && efectivoRecibido.value < aplicadoEfectivo.value) {
    error.value = 'El efectivo recibido no cubre el monto.'
    return
  }
  const pagos: Record<string, string>[] = []
  if (aplicadoEfectivo.value > 0) {
    pagos.push({
      metodo: 'efectivo',
      monto: aplicadoEfectivo.value.toFixed(2),
      recibido: efectivoRecibido.value.toFixed(2),
    })
  }
  if (qrMonto.value > 0) {
    pagos.push({ metodo: 'qr', monto: qrMonto.value.toFixed(2), referencia: qrReferencia.value })
  }

  enviando.value = true
  try {
    const { data } = await http.post<Venta>('/ventas/', {
      sucursal: auth.sucursalActivaId,
      referencia_cliente: pos.referencia,
      items: pos.lineas.map((l) => ({ presentacion: l.presentacionId, cantidad: l.cantidad })),
      pagos,
      descuento: pos.descuento.toFixed(2),
      receta_numero: pos.recetaNumero,
      medico: pos.medico,
      cliente: { numero_documento: pos.clienteDocumento, razon_social: pos.clienteNombre },
    })

    const pagoQr = data.pagos.find((p) => p.metodo === 'qr')
    if (pagoQr && comprobante.value) {
      const form = new FormData()
      form.append('comprobante', comprobante.value)
      try {
        await http.post(`/pagos/${pagoQr.id}/comprobante/`, form)
      } catch {
        aviso.value = 'La venta se registro, pero no se pudo subir el comprobante QR.'
      }
    }

    ticket.value = data
    cobrando.value = false
    pos.vaciar()
    await buscar() // refresca el stock mostrado
  } catch (e) {
    error.value = mensajeError(e)
  } finally {
    enviando.value = false
  }
}

function imprimir() {
  window.print()
}

function alTeclear(e: KeyboardEvent) {
  if (e.key === 'F2') {
    e.preventDefault()
    inputBusqueda.value?.focus()
  } else if (e.key === 'F4') {
    e.preventDefault()
    abrirCobro()
  }
}

onMounted(() => {
  window.addEventListener('keydown', alTeclear)
  cargarTurno()
  inputBusqueda.value?.focus()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', alTeclear)
  clearTimeout(temporizador)
})
</script>

<template>
  <section class="space-y-3">
    <div
      v-if="!cargandoTurno && !turno"
      class="card flex items-center justify-between border-warn p-3 text-sm"
      role="alert"
    >
      <span>Debes abrir un turno de caja para poder vender.</span>
      <RouterLink :to="{ name: 'caja' }" class="btn-primary">Abrir caja</RouterLink>
    </div>
    <p v-if="aviso" class="card border-warn p-3 text-sm" role="status">{{ aviso }}</p>

    <div class="grid gap-4 lg:grid-cols-[1fr_24rem]">
      <!-- Busqueda y resultados -->
      <div class="space-y-3">
        <div class="relative">
          <i class="pi pi-search absolute left-3 top-3 text-slate-400" aria-hidden="true"></i>
          <input
            ref="inputBusqueda"
            v-model="q"
            class="input !py-3 !pl-10 text-base"
            type="search"
            placeholder="Nombre comercial, principio activo o codigo de barras  (F2)"
            autocomplete="off"
            @keydown.enter.prevent="alEnter"
          />
        </div>
        <p v-if="error && !cobrando" class="text-sm text-danger" role="alert">{{ error }}</p>
        <p v-if="buscando" class="text-sm text-slate-500">Buscando...</p>
        <p v-else-if="q.trim().length >= 2 && !resultados.length" class="text-sm text-slate-500">
          Sin resultados.
        </p>

        <div class="grid gap-3 sm:grid-cols-2">
          <article v-for="p in resultados" :key="p.id" class="card flex gap-3 p-3">
            <div
              class="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-slate-100 dark:bg-slate-700"
            >
              <img
                v-if="p.imagen"
                :src="p.imagen"
                :alt="p.nombre"
                class="h-full w-full object-cover"
              />
              <i v-else class="pi pi-image text-2xl text-slate-400" aria-hidden="true"></i>
            </div>
            <div class="min-w-0 flex-1">
              <h3 class="truncate font-semibold">
                {{ p.nombre }} <span class="font-normal">{{ p.concentracion }}</span>
              </h3>
              <p class="truncate text-xs text-slate-500">
                {{ p.principio_activo }} · {{ p.forma }}
              </p>
              <p class="mt-0.5 text-xs">
                <span
                  v-if="p.stock_base > 0"
                  class="font-medium text-brand-600 dark:text-brand-400"
                >
                  Stock:
                  {{
                    base(
                      p.stock_base,
                      p.presentaciones.find((x) => x.nivel === 'caja')?.factor,
                      p.unidad_base,
                    )
                  }}
                </span>
                <span v-else class="font-medium text-danger">Sin stock</span>
                <span v-if="p.proximo_vencimiento" class="text-slate-500">
                  · vence {{ fecha(p.proximo_vencimiento) }}</span
                >
              </p>
              <p v-if="p.es_controlado || p.requiere_receta" class="text-xs font-medium text-warn">
                <i class="pi pi-exclamation-triangle" aria-hidden="true"></i>
                {{ p.es_controlado ? 'Controlado: exige receta' : 'Venta con receta' }}
              </p>
              <div class="mt-2 flex flex-wrap gap-1.5">
                <button
                  v-for="x in p.presentaciones"
                  :key="x.id"
                  type="button"
                  class="btn-ghost !px-2 !py-1 text-xs"
                  :disabled="x.disponible < 1"
                  :title="`${x.factor} ${p.unidad_base} · disponibles: ${x.disponible}`"
                  @click="pos.agregar(p, x)"
                >
                  {{ x.nombre }} · {{ bs(x.precio) }}
                </button>
              </div>
            </div>
          </article>
        </div>
      </div>

      <!-- Carrito -->
      <aside class="card flex h-fit flex-col p-3 lg:sticky lg:top-28">
        <h2 class="mb-2 font-semibold">Carrito ({{ pos.cantidadItems }})</h2>
        <p v-if="!pos.lineas.length" class="py-6 text-center text-sm text-slate-500">
          Agrega productos desde la busqueda.
        </p>
        <ul v-else class="max-h-[50vh] space-y-2 overflow-y-auto">
          <li
            v-for="l in pos.lineas"
            :key="l.presentacionId"
            class="rounded-lg border border-slate-200 p-2 dark:border-slate-700"
            :class="pos.excedeStock(l) ? '!border-danger' : ''"
          >
            <div class="flex justify-between gap-2 text-sm">
              <span class="font-medium">{{ l.nombre }}</span>
              <button
                type="button"
                class="text-slate-400 hover:text-danger"
                aria-label="Quitar"
                @click="pos.quitar(l.presentacionId)"
              >
                <i class="pi pi-trash" aria-hidden="true"></i>
              </button>
            </div>
            <div class="mt-1 flex items-center justify-between text-xs text-slate-500">
              <span>{{ l.presentacion }} · {{ bs(l.precio) }}</span>
              <span class="font-semibold text-slate-800 dark:text-slate-100">{{
                bs(l.precio * l.cantidad)
              }}</span>
            </div>
            <div class="mt-1 flex items-center gap-1">
              <button
                type="button"
                class="btn-ghost !px-2 !py-0.5"
                aria-label="Menos"
                @click="pos.cambiarCantidad(l.presentacionId, l.cantidad - 1)"
              >
                −
              </button>
              <input
                class="input !w-14 !py-0.5 text-center"
                type="number"
                min="1"
                :value="l.cantidad"
                @change="
                  pos.cambiarCantidad(
                    l.presentacionId,
                    Number(($event.target as HTMLInputElement).value),
                  )
                "
              />
              <button
                type="button"
                class="btn-ghost !px-2 !py-0.5"
                aria-label="Mas"
                @click="pos.cambiarCantidad(l.presentacionId, l.cantidad + 1)"
              >
                +
              </button>
            </div>
            <p v-if="pos.excedeStock(l)" class="mt-1 text-xs text-danger">
              Supera el stock disponible.
            </p>
          </li>
        </ul>

        <div class="mt-3 space-y-1 border-t border-slate-200 pt-3 text-sm dark:border-slate-700">
          <div class="flex justify-between">
            <span>Subtotal</span><span>{{ bs(pos.subtotal) }}</span>
          </div>
          <label v-if="puedeDescontar" class="flex items-center justify-between gap-2">
            <span>Descuento (Bs)</span>
            <input
              v-model.number="pos.descuento"
              class="input !w-24 !py-0.5 text-right"
              type="number"
              min="0"
              step="0.01"
            />
          </label>
          <div class="flex justify-between text-lg font-bold">
            <span>Total</span
            ><span class="text-brand-600 dark:text-brand-400">{{ bs(pos.total) }}</span>
          </div>
        </div>

        <button
          type="button"
          class="btn-primary mt-3 !py-3 text-base"
          :disabled="!puedeCobrar"
          @click="abrirCobro"
        >
          Cobrar (F4)
        </button>
        <button v-if="pos.lineas.length" type="button" class="btn-ghost mt-2" @click="pos.vaciar()">
          Vaciar carrito
        </button>
      </aside>
    </div>

    <!-- Cobro -->
    <Modal v-if="cobrando" titulo="Cobrar venta" @cerrar="cobrando = false">
      <form class="space-y-3" @submit.prevent="confirmarVenta">
        <p class="text-center text-3xl font-bold text-brand-600 dark:text-brand-400">
          {{ bs(pos.total) }}
        </p>

        <div class="grid grid-cols-2 gap-3">
          <label class="text-sm">
            <span class="mb-1 block font-medium">Pago QR / transferencia</span>
            <input
              v-model.number="qrMonto"
              class="input"
              type="number"
              min="0"
              :max="pos.total"
              step="0.01"
            />
          </label>
          <label class="text-sm">
            <span class="mb-1 block font-medium">Efectivo recibido</span>
            <input
              v-model.number="efectivoRecibido"
              class="input"
              type="number"
              :min="aplicadoEfectivo"
              step="0.01"
              :disabled="aplicadoEfectivo <= 0"
              autofocus
            />
          </label>
        </div>

        <div class="rounded-lg bg-slate-100 p-3 text-sm dark:bg-slate-700/50">
          <div class="flex justify-between">
            <span>Efectivo a cobrar</span><span>{{ bs(Math.max(0, aplicadoEfectivo)) }}</span>
          </div>
          <div class="flex justify-between text-base font-bold">
            <span>Vuelto</span><span>{{ bs(Math.max(0, vuelto)) }}</span>
          </div>
        </div>

        <div v-if="qrMonto > 0" class="grid gap-3 sm:grid-cols-2">
          <label class="text-sm">
            <span class="mb-1 block font-medium">Referencia de la transaccion</span>
            <input v-model="qrReferencia" class="input" maxlength="80" />
          </label>
          <label class="text-sm">
            <span class="mb-1 block font-medium">Comprobante (opcional)</span>
            <input class="input" type="file" accept="image/*" @change="alElegirArchivo" />
          </label>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <label class="text-sm">
            <span class="mb-1 block font-medium"
              >CI / NIT del cliente{{ pos.esControlado ? ' *' : '' }}</span
            >
            <input
              v-model="pos.clienteDocumento"
              class="input"
              maxlength="30"
              :required="pos.esControlado"
            />
          </label>
          <label class="text-sm">
            <span class="mb-1 block font-medium">Nombre / razon social</span>
            <input v-model="pos.clienteNombre" class="input" maxlength="150" />
          </label>
        </div>

        <div
          v-if="pos.requiereReceta"
          class="grid gap-3 rounded-lg border border-warn p-3 sm:grid-cols-2"
        >
          <label class="text-sm">
            <span class="mb-1 block font-medium">N° de receta *</span>
            <input v-model="pos.recetaNumero" class="input" maxlength="60" required />
          </label>
          <label class="text-sm">
            <span class="mb-1 block font-medium">Medico{{ pos.esControlado ? ' *' : '' }}</span>
            <input
              v-model="pos.medico"
              class="input"
              maxlength="120"
              :required="pos.esControlado"
            />
          </label>
        </div>

        <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn-ghost" @click="cobrando = false">Cancelar</button>
          <button type="submit" class="btn-primary" :disabled="enviando">
            {{ enviando ? 'Registrando...' : 'Confirmar venta' }}
          </button>
        </div>
      </form>
    </Modal>

    <!-- Recibo -->
    <Modal v-if="ticket" titulo="Venta registrada" ancho="max-w-sm" @cerrar="ticket = null">
      <TicketVenta :venta="ticket" />
      <div class="mt-4 flex justify-end gap-2 print:hidden">
        <button type="button" class="btn-ghost" @click="ticket = null">Cerrar</button>
        <button type="button" class="btn-primary" @click="imprimir">
          <i class="pi pi-print" aria-hidden="true"></i> Imprimir
        </button>
      </div>
    </Modal>
  </section>
</template>
