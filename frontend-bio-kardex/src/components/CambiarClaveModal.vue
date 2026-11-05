<script setup lang="ts">
import { ref } from 'vue'
import { http } from '@/api/http'
import Modal from '@/components/Modal.vue'
import { mensajeError } from '@/utils/errores'

const emit = defineEmits<{ cerrar: [] }>()

const actual = ref('')
const nueva = ref('')
const repetir = ref('')
const error = ref('')
const listo = ref(false)
const guardando = ref(false)

async function guardar() {
  error.value = ''
  if (nueva.value !== repetir.value) {
    error.value = 'Las contrasenas nuevas no coinciden.'
    return
  }
  guardando.value = true
  try {
    await http.post('/auth/cambiar-clave/', { clave_actual: actual.value, clave_nueva: nueva.value })
    listo.value = true
  } catch (e) {
    error.value = mensajeError(e)
  } finally {
    guardando.value = false
  }
}
</script>

<template>
  <Modal titulo="Cambiar contrasena" ancho="max-w-sm" @cerrar="emit('cerrar')">
    <p v-if="listo" class="text-sm text-brand-600" role="status">Contrasena actualizada.</p>
    <form v-else class="space-y-3" @submit.prevent="guardar">
      <label class="block text-sm">
        <span class="mb-1 block font-medium">Contrasena actual</span>
        <input v-model="actual" class="input" type="password" autocomplete="current-password" required />
      </label>
      <label class="block text-sm">
        <span class="mb-1 block font-medium">Contrasena nueva</span>
        <input v-model="nueva" class="input" type="password" autocomplete="new-password" required minlength="8" />
      </label>
      <label class="block text-sm">
        <span class="mb-1 block font-medium">Repetir contrasena nueva</span>
        <input v-model="repetir" class="input" type="password" autocomplete="new-password" required />
      </label>
      <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>
      <div class="flex justify-end gap-2">
        <button type="button" class="btn-ghost" @click="emit('cerrar')">Cancelar</button>
        <button type="submit" class="btn-primary" :disabled="guardando">Guardar</button>
      </div>
    </form>
    <div v-if="listo" class="mt-4 flex justify-end">
      <button type="button" class="btn-primary" @click="emit('cerrar')">Cerrar</button>
    </div>
  </Modal>
</template>
