<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold">Hola, {{ auth.nombre }}</h1>
    <div class="card p-4">
      <p class="text-sm text-slate-500 dark:text-slate-400">Sucursal activa</p>
      <p class="text-lg font-medium">
        {{ auth.sucursalActiva?.nombre ?? 'Sin sucursal asignada' }}
      </p>
    </div>
    <p class="text-slate-500 dark:text-slate-400">
      Fundaciones listas. Los modulos de catalogo, inventario, caja y POS se agregan en las
      siguientes fases.
    </p>
  </section>
</template>
