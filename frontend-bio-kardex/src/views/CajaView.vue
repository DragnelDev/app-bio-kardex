<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { http } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { mensajeError } from '@/utils/errores'
import { bs, fechaHora, redondear } from '@/utils/format'
import type { Caja, Paginado, TotalesTurno, Turno } from '@/types'

const auth = useAuthStore()

const turno = ref<Turno | null>(null)
const totales = ref<TotalesTurno | null>(null)
const cajas = ref<Caja[]>([])
const historial = ref<Turno[]>([])
const cargando = ref(true)
const error = ref('')
const cerrado = ref<{ turno: Turno; totales: TotalesTurno } | null>(null)

const cajaElegida = ref<number | null>(null)
const fondo = ref(0)

const efectivoContado = ref(0)
const qrContado = ref(0)
const observaciones = ref('')

const sucursal = computed(() => auth.sucursalActivaId)
const difEfectivo = computed(() =>
  totales.value ? redondear(efectivoContado.value - Number(totales.value.efectivo_esperado)) : 0,
)
const difQr = computed(() =>
  totales.value ? redondear(qrContado.value - Number(totales.value.qr_esperado)) : 0,
)

async function cargar() {
  if (!sucursal.value) return
  cargando.value = true
  error.value = ''
  try {
    const { data } = await http.get<{ turno: Turno | null; totales?: TotalesTurno }>(
      '/turnos/actual/',
      {
        params: { sucursal: sucursal.value },
      },
    )
    turno.value = data.turno
    totales.value = data.totales ?? null
    if (!data.turno) {
      const r = await http.get<Paginado<Caja>>('/cajas/', { params: { sucursal: sucursal.value } })
      cajas.value = r.data.results.filter((c) => c.activa)
      cajaElegida.value = cajas.value[0]?.id ?? null
    } else {
      efectivoContado.value = 0
      qrContado.value = 0
    }
    const h = await http.get<Paginado<Turno>>('/turnos/', {
      params: { sucursal: sucursal.value, page_size: 10 },
    })
    historial.value = h.data.results.filter((t) => !t.abierto)
  } catch (e) {
    error.value = mensajeError(e)
  } finally {
    cargando.value = false
  }
}

async function abrir() {
  error.value = ''
  if (!cajaElegida.value) {
    error.value = 'Elige una caja.'
    return
  }
  try {
    await http.post('/turnos/', { caja: cajaElegida.value, fondo_inicial: fondo.value.toFixed(2) })
    cerrado.value = null
    await cargar()
  } catch (e) {
    error.value = mensajeError(e)
  }
}

async function cerrar() {
  if (!turno.value) return
  if (!window.confirm('Cerrar el turno y registrar el arqueo?')) return
  error.value = ''
  try {
    const { data } = await http.post<{ turno: Turno; totales: TotalesTurno }>(
      `/turnos/${turno.value.id}/cerrar/`,
      {
        efectivo_contado: efectivoContado.value.toFixed(2),
        qr_contado: qrContado.value.toFixed(2),
        observaciones: observaciones.value,
      },
    )
    cerrado.value = data
    observaciones.value = ''
    await cargar()
  } catch (e) {
    error.value = mensajeError(e)
  }
}

const nombreNuevaCaja = ref('')

async function crearCaja() {
  if (!sucursal.value || !nombreNuevaCaja.value.trim()) return
  error.value = ''
  try {
    await http.post('/cajas/', {
      sucursal: sucursal.value,
      nombre: nombreNuevaCaja.value.trim(),
      activa: true,
    })
    nombreNuevaCaja.value = ''
    await cargar()
  } catch (e) {
    error.value = mensajeError(e)
  }
}

function claseDif(n: number) {
  return n === 0 ? 'text-brand-600' : 'text-danger'
}

onMounted(cargar)
</script>

<template>
  <section class="mx-auto max-w-3xl space-y-4">
    <h1 class="text-2xl font-semibold">Caja</h1>
    <p v-if="error" class="card border-danger p-3 text-sm text-danger" role="alert">{{ error }}</p>
    <p v-if="cargando" class="text-slate-500">Cargando...</p>

    <!-- Arqueo del turno que acaba de cerrarse -->
    <div v-if="cerrado" class="card space-y-2 border-brand-500 p-4">
      <h2 class="font-semibold">Turno cerrado</h2>
      <div class="grid grid-cols-3 gap-2 text-sm">
        <span></span><span class="font-medium">Efectivo</span><span class="font-medium">QR</span>
        <span>Esperado</span><span>{{ bs(cerrado.turno.efectivo_esperado) }}</span
        ><span>{{ bs(cerrado.turno.qr_esperado) }}</span> <span>Contado</span
        ><span>{{ bs(cerrado.turno.efectivo_contado) }}</span
        ><span>{{ bs(cerrado.turno.qr_contado) }}</span>
        <span>Diferencia</span>
        <span :class="claseDif(Number(cerrado.turno.diferencia_efectivo))">{{
          bs(cerrado.turno.diferencia_efectivo)
        }}</span>
        <span :class="claseDif(Number(cerrado.turno.diferencia_qr))">{{
          bs(cerrado.turno.diferencia_qr)
        }}</span>
      </div>
    </div>

    <!-- Abrir turno -->
    <form v-if="!cargando && !turno" class="card space-y-3 p-4" @submit.prevent="abrir">
      <h2 class="font-semibold">Abrir turno</h2>
      <div v-if="!cajas.length" class="text-sm text-slate-500">
        <p>No hay cajas activas en esta sucursal.</p>
        <div v-if="auth.puede(['regente'])" class="mt-2 flex gap-2">
          <input
            v-model="nombreNuevaCaja"
            class="input !w-48"
            placeholder="Nombre (Caja 1)"
            maxlength="60"
          />
          <button type="button" class="btn-ghost" @click="crearCaja">Crear caja</button>
        </div>
        <p v-else>Un regente o administrador debe crear una.</p>
      </div>
      <div class="grid gap-3 sm:grid-cols-2">
        <label class="text-sm">
          <span class="mb-1 block font-medium">Caja</span>
          <select v-model="cajaElegida" class="input">
            <option v-for="c in cajas" :key="c.id" :value="c.id">{{ c.nombre }}</option>
          </select>
        </label>
        <label class="text-sm">
          <span class="mb-1 block font-medium">Fondo inicial (efectivo)</span>
          <input v-model.number="fondo" class="input" type="number" min="0" step="0.01" required />
        </label>
      </div>
      <button type="submit" class="btn-primary" :disabled="!cajas.length">Abrir turno</button>
    </form>

    <!-- Turno abierto -->
    <template v-if="turno && totales">
      <div class="card p-4">
        <h2 class="mb-1 font-semibold">
          {{ turno.caja_nombre }} · abierto {{ fechaHora(turno.abierto_en) }}
        </h2>
        <dl class="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
          <dt class="text-slate-500">Fondo inicial</dt>
          <dd class="text-right sm:text-left">{{ bs(totales.fondo_inicial) }}</dd>
          <dt class="text-slate-500">Ventas en efectivo</dt>
          <dd class="text-right sm:text-left">{{ bs(totales.ventas_efectivo) }}</dd>
          <dt class="text-slate-500">Ventas QR</dt>
          <dd class="text-right sm:text-left">{{ bs(totales.ventas_qr) }}</dd>
          <dt class="text-slate-500">Devoluciones efectivo</dt>
          <dd class="text-right sm:text-left">{{ bs(totales.devoluciones_efectivo) }}</dd>
          <dt class="text-slate-500">Devoluciones QR</dt>
          <dd class="text-right sm:text-left">{{ bs(totales.devoluciones_qr) }}</dd>
        </dl>
      </div>

      <form class="card space-y-3 p-4" @submit.prevent="cerrar">
        <h2 class="font-semibold">Cerrar turno y arquear</h2>
        <p class="text-xs text-slate-500">
          Cuenta el efectivo fisico de la caja y verifica el total recibido por QR. El sistema
          compara contra lo esperado.
        </p>
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="text-sm">
            <span class="mb-1 block font-medium">Efectivo contado</span>
            <input
              v-model.number="efectivoContado"
              class="input"
              type="number"
              min="0"
              step="0.01"
              required
            />
            <span class="text-xs" :class="claseDif(difEfectivo)">
              Diferencia: {{ bs(difEfectivo) }} (esperado {{ bs(totales.efectivo_esperado) }})
            </span>
          </label>
          <label class="text-sm">
            <span class="mb-1 block font-medium">QR verificado</span>
            <input
              v-model.number="qrContado"
              class="input"
              type="number"
              min="0"
              step="0.01"
              required
            />
            <span class="text-xs" :class="claseDif(difQr)">
              Diferencia: {{ bs(difQr) }} (esperado {{ bs(totales.qr_esperado) }})
            </span>
          </label>
        </div>
        <label class="block text-sm">
          <span class="mb-1 block font-medium">Observaciones</span>
          <input v-model="observaciones" class="input" maxlength="255" />
        </label>
        <button type="submit" class="btn-danger">Cerrar turno</button>
      </form>
    </template>

    <div v-if="historial.length" class="card overflow-x-auto">
      <h2 class="p-4 pb-0 font-semibold">Ultimos turnos cerrados</h2>
      <table class="w-full">
        <thead>
          <tr>
            <th class="th">Cierre</th>
            <th class="th">Cajero</th>
            <th class="th">Dif. efectivo</th>
            <th class="th">Dif. QR</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="t in historial"
            :key="t.id"
            class="border-t border-slate-200 dark:border-slate-700"
          >
            <td class="td">{{ fechaHora(t.cerrado_en) }}</td>
            <td class="td">{{ t.cajero_nombre }}</td>
            <td class="td" :class="claseDif(Number(t.diferencia_efectivo))">
              {{ bs(t.diferencia_efectivo) }}
            </td>
            <td class="td" :class="claseDif(Number(t.diferencia_qr))">{{ bs(t.diferencia_qr) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
