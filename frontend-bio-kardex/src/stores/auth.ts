import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { http, borrarTokens, guardarTokens, leerToken } from '@/api/http'

export type Rol = 'admin' | 'regente' | 'cajero' | 'almacenero'

export interface Sucursal {
  id: number
  codigo: string
  nombre: string
  ciudad: string
  es_casa_matriz: boolean
  activa: boolean
}

export interface Usuario {
  id: number
  username: string
  first_name: string
  last_name: string
  email: string
  rol: Rol
  sucursales: Sucursal[]
}

const SUCURSAL_KEY = 'bk-sucursal'

export const useAuthStore = defineStore('auth', () => {
  const usuario = ref<Usuario | null>(null)
  const sucursalActivaId = ref<number | null>(null)
  const cargado = ref(false)

  const autenticado = computed(() => usuario.value !== null)
  const esAdmin = computed(() => usuario.value?.rol === 'admin')
  const nombre = computed(() => {
    const u = usuario.value
    if (!u) return ''
    return `${u.first_name} ${u.last_name}`.trim() || u.username
  })
  const sucursalActiva = computed(
    () => usuario.value?.sucursales.find((s) => s.id === sucursalActivaId.value) ?? null,
  )

  /** true si el usuario es admin o su rol esta en la lista (sin lista = cualquiera). */
  function puede(roles?: Rol[]): boolean {
    if (!usuario.value) return false
    if (!roles || roles.length === 0) return true
    return usuario.value.rol === 'admin' || roles.includes(usuario.value.rol)
  }

  function fijarUsuario(u: Usuario) {
    usuario.value = u
    let guardada: number | null = null
    try {
      guardada = Number(localStorage.getItem(SUCURSAL_KEY)) || null
    } catch {
      /* ignorar */
    }
    const valida = u.sucursales.some((s) => s.id === guardada)
    sucursalActivaId.value = valida ? guardada : (u.sucursales[0]?.id ?? null)
  }

  function elegirSucursal(id: number) {
    sucursalActivaId.value = id
    try {
      localStorage.setItem(SUCURSAL_KEY, String(id))
    } catch {
      /* ignorar */
    }
  }

  async function login(username: string, password: string) {
    const { data } = await http.post('/auth/login/', { username, password })
    guardarTokens(data.access, data.refresh)
    fijarUsuario(data.usuario as Usuario)
    cargado.value = true
  }

  /** Restaura la sesion si hay tokens guardados. */
  async function restaurar() {
    if (cargado.value) return
    if (leerToken('access') || leerToken('refresh')) {
      try {
        const { data } = await http.get('/auth/me/')
        fijarUsuario(data as Usuario)
      } catch {
        borrarTokens()
        usuario.value = null
      }
    }
    cargado.value = true
  }

  function logout() {
    borrarTokens()
    usuario.value = null
    sucursalActivaId.value = null
  }

  return {
    usuario,
    cargado,
    autenticado,
    esAdmin,
    nombre,
    sucursalActiva,
    sucursalActivaId,
    puede,
    login,
    restaurar,
    logout,
    elegirSucursal,
  }
})
