<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

function sesionExpirada() {
  auth.logout()
  router.push({ name: 'login' })
}

onMounted(() => window.addEventListener('bk:sesion-expirada', sesionExpirada))
onBeforeUnmount(() => window.removeEventListener('bk:sesion-expirada', sesionExpirada))
</script>

<template>
  <RouterView />
</template>
