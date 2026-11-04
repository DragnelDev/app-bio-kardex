<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ThemeToggle from '@/components/ThemeToggle.vue'

const auth = useAuthStore()
const router = useRouter()

const enlaces = computed(() =>
  router
    .getRoutes()
    .filter((r) => r.meta.menu && auth.puede(r.meta.roles))
    .map((r) => ({
      nombre: r.name as string,
      titulo: r.meta.titulo ?? '',
      icono: r.meta.icono ?? '',
    })),
)

function salir() {
  auth.logout()
  router.push({ name: 'login' })
}

function cambiarSucursal(e: Event) {
  auth.elegirSucursal(Number((e.target as HTMLSelectElement).value))
}
</script>

<template>
  <div class="min-h-screen">
    <header
      class="sticky top-0 z-30 border-b border-slate-200 bg-surface dark:border-slate-700 dark:bg-surface-dark print:hidden"
    >
      <div class="flex items-center gap-3 px-4 py-2">
        <div class="flex items-center gap-2 font-semibold">
          <span class="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500 text-white">
            <i class="pi pi-plus" aria-hidden="true"></i>
          </span>
          BioKardex
        </div>

        <div class="ml-auto flex items-center gap-3">
          <label v-if="auth.usuario?.sucursales.length" class="flex items-center gap-2 text-sm">
            <span class="sr-only">Sucursal</span>
            <i class="pi pi-building text-slate-500" aria-hidden="true"></i>
            <select
              class="rounded-lg border border-slate-300 bg-transparent px-2 py-1 dark:border-slate-600 dark:bg-surface-dark"
              :value="auth.sucursalActivaId ?? ''"
              @change="cambiarSucursal"
            >
              <option v-for="s in auth.usuario.sucursales" :key="s.id" :value="s.id">
                {{ s.nombre }}
              </option>
            </select>
          </label>
          <span class="hidden text-sm text-slate-500 sm:inline dark:text-slate-400">
            {{ auth.nombre }} · {{ auth.usuario?.rol }}
          </span>
          <ThemeToggle />
          <button
            type="button"
            class="flex h-9 w-9 items-center justify-center rounded-lg text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
            aria-label="Cerrar sesion"
            @click="salir"
          >
            <i class="pi pi-sign-out" aria-hidden="true"></i>
          </button>
        </div>
      </div>

      <nav class="flex gap-1 overflow-x-auto px-3 pb-2" aria-label="Principal">
        <RouterLink
          v-for="e in enlaces"
          :key="e.nombre"
          :to="{ name: e.nombre }"
          class="flex shrink-0 items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700"
          active-class="!bg-brand-500/15 !text-brand-700 dark:!text-brand-400 font-medium"
          exact-active-class="!bg-brand-500/15 !text-brand-700 dark:!text-brand-400 font-medium"
        >
          <i :class="['pi', e.icono]" aria-hidden="true"></i>
          {{ e.titulo }}
        </RouterLink>
      </nav>
    </header>

    <main class="mx-auto max-w-7xl p-4">
      <p v-if="!auth.sucursalActiva" class="card mb-4 border-warn p-4 text-sm" role="alert">
        No tienes una sucursal asignada. Pide a un administrador que te asigne una.
      </p>
      <RouterView v-else :key="auth.sucursalActivaId ?? 0" />
    </main>
  </div>
</template>
