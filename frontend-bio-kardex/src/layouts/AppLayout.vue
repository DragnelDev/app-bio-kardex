<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ThemeToggle from '@/components/ThemeToggle.vue'

const auth = useAuthStore()
const router = useRouter()

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
      class="sticky top-0 z-10 flex items-center gap-3 border-b border-slate-200 bg-surface px-4 py-2 dark:border-slate-700 dark:bg-surface-dark"
    >
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
    </header>

    <main class="mx-auto max-w-6xl p-4">
      <RouterView />
    </main>
  </div>
</template>
