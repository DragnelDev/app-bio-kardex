<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { isAxiosError } from 'axios'
import { useAuthStore } from '@/stores/auth'
import ThemeToggle from '@/components/ThemeToggle.vue'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const cargando = ref(false)
const error = ref('')

async function enviar() {
  error.value = ''
  cargando.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    const destino = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.push(destino.startsWith('/') ? destino : '/')
  } catch (e) {
    error.value =
      isAxiosError(e) && e.response?.status === 401
        ? 'Usuario o contrasena incorrectos.'
        : 'No se pudo iniciar sesion. Intenta de nuevo.'
  } finally {
    cargando.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center p-4">
    <div class="absolute right-4 top-4"><ThemeToggle /></div>

    <form class="card w-full max-w-sm space-y-4 p-6" @submit.prevent="enviar">
      <div class="flex items-center gap-3">
        <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-white">
          <i class="pi pi-plus" aria-hidden="true"></i>
        </span>
        <div>
          <h1 class="text-xl font-semibold leading-tight">BioKardex</h1>
          <p class="text-sm text-slate-500 dark:text-slate-400">Inicia sesion para continuar</p>
        </div>
      </div>

      <label class="block text-sm">
        <span class="mb-1 block font-medium">Usuario</span>
        <input
          v-model="username"
          type="text"
          autocomplete="username"
          required
          autofocus
          class="w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-600"
        />
      </label>

      <label class="block text-sm">
        <span class="mb-1 block font-medium">Contrasena</span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          class="w-full rounded-lg border border-slate-300 bg-transparent px-3 py-2 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 dark:border-slate-600"
        />
      </label>

      <p v-if="error" role="alert" class="text-sm text-danger">{{ error }}</p>

      <button
        type="submit"
        :disabled="cargando"
        class="w-full rounded-lg bg-brand-500 px-4 py-2 font-medium text-white transition hover:bg-brand-600 disabled:opacity-60"
      >
        {{ cargando ? 'Ingresando...' : 'Ingresar' }}
      </button>
    </form>
  </div>
</template>
