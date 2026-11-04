<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { http } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { bs } from '@/utils/format'
import type { StockItem, TotalesTurno, Turno } from '@/types'

const auth = useAuthStore()

const vencidos = ref(0)
const porVencer = ref(0)
const bajoMinimo = ref<{ producto: string; stock: number; stock_minimo: number }[]>([])
const turno = ref<Turno | null>(null)
const totales = ref<TotalesTurno | null>(null)
const cargando = ref(true)

onMounted(async () => {
  const sucursal = auth.sucursalActivaId
  if (!sucursal) return
  const tareas: Promise<unknown>[] = []
  if (auth.puede(['regente', 'almacenero'])) {
    tareas.push(
      http
        .get<{ vencidos: StockItem[]; por_vencer: StockItem[] }>('/inventario/alertas/', {
          params: { sucursal },
        })
        .then(({ data }) => {
          vencidos.value = data.vencidos.length
          porVencer.value = data.por_vencer.length
        }),
      http
        .get<{ bajo_minimo: typeof bajoMinimo.value }>('/inventario/resumen/', {
          params: { sucursal },
        })
        .then(({ data }) => (bajoMinimo.value = data.bajo_minimo)),
    )
  }
  if (auth.puede(['cajero', 'regente'])) {
    tareas.push(
      http
        .get<{ turno: Turno | null; totales?: TotalesTurno }>('/turnos/actual/', {
          params: { sucursal },
        })
        .then(({ data }) => {
          turno.value = data.turno
          totales.value = data.totales ?? null
        }),
    )
  }
  await Promise.allSettled(tareas)
  cargando.value = false
})
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold">Hola, {{ auth.nombre }}</h1>
    <p class="text-slate-500 dark:text-slate-400">
      Sucursal: <strong>{{ auth.sucursalActiva?.nombre }}</strong>
    </p>

    <div v-if="!cargando" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <RouterLink
        v-if="auth.puede(['regente', 'almacenero'])"
        :to="{ name: 'inventario' }"
        class="card p-4"
      >
        <p class="text-sm text-slate-500">Lotes vencidos con stock</p>
        <p class="text-3xl font-semibold" :class="vencidos ? 'text-danger' : ''">{{ vencidos }}</p>
      </RouterLink>
      <RouterLink
        v-if="auth.puede(['regente', 'almacenero'])"
        :to="{ name: 'inventario' }"
        class="card p-4"
      >
        <p class="text-sm text-slate-500">Lotes por vencer</p>
        <p class="text-3xl font-semibold" :class="porVencer ? 'text-warn' : ''">{{ porVencer }}</p>
      </RouterLink>
      <div v-if="auth.puede(['regente', 'almacenero'])" class="card p-4">
        <p class="text-sm text-slate-500">Productos bajo el minimo</p>
        <p class="text-3xl font-semibold">{{ bajoMinimo.length }}</p>
      </div>
      <RouterLink v-if="auth.puede(['cajero', 'regente'])" :to="{ name: 'caja' }" class="card p-4">
        <p class="text-sm text-slate-500">Mi turno de caja</p>
        <template v-if="turno && totales">
          <p class="text-lg font-semibold text-brand-600">Abierto</p>
          <p class="text-sm text-slate-500">
            Efectivo esperado: {{ bs(totales.efectivo_esperado) }}
          </p>
        </template>
        <p v-else class="text-lg font-semibold">Sin abrir</p>
      </RouterLink>
    </div>

    <div v-if="bajoMinimo.length" class="card p-4">
      <h2 class="mb-2 font-semibold">Reponer pronto</h2>
      <ul class="space-y-1 text-sm">
        <li v-for="b in bajoMinimo" :key="b.producto" class="flex justify-between">
          <span>{{ b.producto }}</span>
          <span class="text-slate-500">{{ b.stock }} / min. {{ b.stock_minimo }}</span>
        </li>
      </ul>
    </div>
  </section>
</template>
