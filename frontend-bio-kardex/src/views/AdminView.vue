<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { http } from '@/api/http'
import { useAuthStore, type Rol } from '@/stores/auth'
import Modal from '@/components/Modal.vue'
import { mensajeError } from '@/utils/errores'
import type { Caja, Paginado } from '@/types'

interface SucursalAdmin {
  id: number
  codigo: string
  nombre: string
  direccion: string
  ciudad: string
  telefono: string
  es_casa_matriz: boolean
  activa: boolean
}
interface UsuarioAdmin {
  id: number
  username: string
  first_name: string
  last_name: string
  email: string
  rol: Rol
  ci: string
  telefono: string
  sucursales: number[]
  is_active: boolean
}

const ROLES: { id: Rol; texto: string }[] = [
  { id: 'admin', texto: 'Administrador' },
  { id: 'regente', texto: 'Regente farmaceutico' },
  { id: 'cajero', texto: 'Cajero' },
  { id: 'almacenero', texto: 'Almacenero' },
]
const etiquetaRol = (r: Rol) => ROLES.find((x) => x.id === r)?.texto ?? r

const auth = useAuthStore()
const pestana = ref<'usuarios' | 'sucursales' | 'cajas'>('usuarios')
const pestanas = [
  { id: 'usuarios' as const, texto: 'Usuarios' },
  { id: 'sucursales' as const, texto: 'Sucursales' },
  { id: 'cajas' as const, texto: 'Cajas' },
]
const error = ref('')

// ---------------------------------------------------------------- sucursales
const sucursales = ref<SucursalAdmin[]>([])
const nombreSucursal = (id: number) => sucursales.value.find((s) => s.id === id)?.nombre ?? `#${id}`

async function cargarSucursales() {
  const { data } = await http.get<Paginado<SucursalAdmin>>('/sucursales/', { params: { page_size: 200 } })
  sucursales.value = data.results
}

const formSucursal = reactive({
  id: null as number | null,
  codigo: '',
  nombre: '',
  direccion: '',
  ciudad: '',
  telefono: '',
  es_casa_matriz: false,
  activa: true,
})
const modalSucursal = ref(false)
const errorSucursal = ref('')

function abrirSucursal(s: SucursalAdmin | null) {
  errorSucursal.value = ''
  Object.assign(
    formSucursal,
    s ?? { id: null, codigo: '', nombre: '', direccion: '', ciudad: '', telefono: '', es_casa_matriz: false, activa: true },
  )
  modalSucursal.value = true
}

async function guardarSucursal() {
  errorSucursal.value = ''
  const { id, ...cuerpo } = formSucursal
  try {
    if (id) await http.patch(`/sucursales/${id}/`, cuerpo)
    else await http.post('/sucursales/', cuerpo)
    modalSucursal.value = false
    await cargarSucursales()
    await auth.refrescarUsuario()
  } catch (e) {
    errorSucursal.value = mensajeError(e)
  }
}

// ------------------------------------------------------------------ usuarios
const usuarios = ref<UsuarioAdmin[]>([])
const filtroQ = ref('')
const filtroRol = ref('')
const filtroActivo = ref('1')

let temporizador: ReturnType<typeof setTimeout> | undefined
watch([filtroQ, filtroRol, filtroActivo], () => {
  clearTimeout(temporizador)
  temporizador = setTimeout(cargarUsuarios, 300)
})

async function cargarUsuarios() {
  try {
    const { data } = await http.get<Paginado<UsuarioAdmin>>('/auth/usuarios/', {
      params: {
        q: filtroQ.value || undefined,
        rol: filtroRol.value || undefined,
        activo: filtroActivo.value || undefined,
        page_size: 100,
      },
    })
    usuarios.value = data.results
  } catch (e) {
    error.value = mensajeError(e)
  }
}

const formUsuario = reactive({
  id: null as number | null,
  username: '',
  password: '',
  first_name: '',
  last_name: '',
  email: '',
  ci: '',
  telefono: '',
  rol: 'cajero' as Rol,
  sucursales: [] as number[],
  is_active: true,
})
const modalUsuario = ref(false)
const errorUsuario = ref('')
const esYo = computed(() => formUsuario.id !== null && formUsuario.id === auth.usuario?.id)

function abrirUsuario(u: UsuarioAdmin | null) {
  errorUsuario.value = ''
  Object.assign(
    formUsuario,
    u
      ? { ...u, password: '', sucursales: [...u.sucursales] }
      : {
          id: null, username: '', password: '', first_name: '', last_name: '', email: '', ci: '',
          telefono: '', rol: 'cajero', sucursales: [], is_active: true,
        },
  )
  modalUsuario.value = true
}

async function guardarUsuario() {
  errorUsuario.value = ''
  const { id, password, ...resto } = formUsuario
  const cuerpo: Record<string, unknown> = { ...resto }
  if (password) cuerpo.password = password
  if (id) delete cuerpo.username
  try {
    if (id) await http.patch(`/auth/usuarios/${id}/`, cuerpo)
    else await http.post('/auth/usuarios/', cuerpo)
    modalUsuario.value = false
    await cargarUsuarios()
  } catch (e) {
    errorUsuario.value = mensajeError(e)
  }
}

// --------------------------------------------------------------------- cajas
const cajas = ref<Caja[]>([])
const sucursalCajas = ref<number | null>(null)
const nombreCaja = ref('')
const errorCajas = ref('')

async function cargarCajas() {
  if (!sucursalCajas.value) {
    cajas.value = []
    return
  }
  const { data } = await http.get<Paginado<Caja>>('/cajas/', {
    params: { sucursal: sucursalCajas.value, page_size: 100 },
  })
  cajas.value = data.results
}
watch(sucursalCajas, cargarCajas)

async function crearCaja() {
  errorCajas.value = ''
  if (!sucursalCajas.value || !nombreCaja.value.trim()) return
  try {
    await http.post('/cajas/', { sucursal: sucursalCajas.value, nombre: nombreCaja.value.trim(), activa: true })
    nombreCaja.value = ''
    await cargarCajas()
  } catch (e) {
    errorCajas.value = mensajeError(e)
  }
}

async function alternarCaja(c: Caja) {
  errorCajas.value = ''
  try {
    await http.patch(`/cajas/${c.id}/`, { activa: !c.activa })
    await cargarCajas()
  } catch (e) {
    errorCajas.value = mensajeError(e)
  }
}

onMounted(async () => {
  try {
    await Promise.all([cargarSucursales(), cargarUsuarios()])
    sucursalCajas.value = sucursales.value.find((s) => s.activa)?.id ?? null
  } catch (e) {
    error.value = mensajeError(e)
  }
})
</script>

<template>
  <section class="space-y-4">
    <h1 class="text-2xl font-semibold">Administracion</h1>

    <div class="flex gap-1 border-b border-slate-200 dark:border-slate-700" role="tablist">
      <button
        v-for="t in pestanas"
        :key="t.id"
        role="tab"
        :aria-selected="pestana === t.id"
        class="-mb-px border-b-2 px-3 py-2 text-sm"
        :class="pestana === t.id ? 'border-brand-500 font-medium text-brand-700 dark:text-brand-400' : 'border-transparent text-slate-500'"
        @click="pestana = t.id"
      >
        {{ t.texto }}
      </button>
    </div>
    <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>

    <!-- Usuarios -->
    <template v-if="pestana === 'usuarios'">
      <div class="flex flex-wrap items-center gap-3">
        <input v-model="filtroQ" class="input !w-56" type="search" placeholder="Buscar usuario, nombre o CI" />
        <select v-model="filtroRol" class="input !w-48">
          <option value="">Todos los roles</option>
          <option v-for="r in ROLES" :key="r.id" :value="r.id">{{ r.texto }}</option>
        </select>
        <select v-model="filtroActivo" class="input !w-36">
          <option value="1">Activos</option><option value="0">Inactivos</option><option value="">Todos</option>
        </select>
        <button type="button" class="btn-primary ml-auto" @click="abrirUsuario(null)"><i class="pi pi-user-plus" aria-hidden="true"></i> Nuevo usuario</button>
      </div>
      <div class="card overflow-x-auto">
        <table class="w-full">
          <thead><tr><th class="th">Usuario</th><th class="th">Nombre</th><th class="th">Rol</th><th class="th">Sucursales</th><th class="th">Estado</th></tr></thead>
          <tbody>
            <tr v-for="u in usuarios" :key="u.id" class="cursor-pointer border-t border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700/40" @click="abrirUsuario(u)">
              <td class="td font-medium">{{ u.username }}</td>
              <td class="td">{{ `${u.first_name} ${u.last_name}`.trim() || '—' }}</td>
              <td class="td">{{ etiquetaRol(u.rol) }}</td>
              <td class="td text-xs text-slate-500">{{ u.rol === 'admin' ? 'Todas' : u.sucursales.map(nombreSucursal).join(', ') || 'Ninguna' }}</td>
              <td class="td"><span :class="u.is_active ? 'text-brand-600' : 'text-danger'">{{ u.is_active ? 'Activo' : 'Inactivo' }}</span></td>
            </tr>
            <tr v-if="!usuarios.length"><td class="td text-slate-500" colspan="5">Sin usuarios.</td></tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Sucursales -->
    <template v-else-if="pestana === 'sucursales'">
      <div class="flex">
        <button type="button" class="btn-primary ml-auto" @click="abrirSucursal(null)"><i class="pi pi-plus" aria-hidden="true"></i> Nueva sucursal</button>
      </div>
      <div class="card overflow-x-auto">
        <table class="w-full">
          <thead><tr><th class="th">Codigo</th><th class="th">Nombre</th><th class="th">Ciudad</th><th class="th">Telefono</th><th class="th">Estado</th></tr></thead>
          <tbody>
            <tr v-for="s in sucursales" :key="s.id" class="cursor-pointer border-t border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700/40" @click="abrirSucursal(s)">
              <td class="td font-medium">{{ s.codigo }}</td>
              <td class="td">{{ s.nombre }} <span v-if="s.es_casa_matriz" class="ml-1 rounded bg-brand-500/15 px-1.5 text-xs">casa matriz</span></td>
              <td class="td">{{ s.ciudad }}</td><td class="td">{{ s.telefono }}</td>
              <td class="td"><span :class="s.activa ? 'text-brand-600' : 'text-danger'">{{ s.activa ? 'Activa' : 'Inactiva' }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p class="text-xs text-slate-500">Las sucursales tienen stock y ventas, por eso no se borran: se desactivan.</p>
    </template>

    <!-- Cajas -->
    <template v-else>
      <div class="flex flex-wrap items-center gap-3">
        <select v-model="sucursalCajas" class="input !w-56">
          <option v-for="s in sucursales.filter((x) => x.activa)" :key="s.id" :value="s.id">{{ s.nombre }}</option>
        </select>
        <input v-model="nombreCaja" class="input !w-48" placeholder="Nombre de la nueva caja" maxlength="60" />
        <button type="button" class="btn-primary" :disabled="!sucursalCajas || !nombreCaja.trim()" @click="crearCaja">Crear caja</button>
      </div>
      <p v-if="errorCajas" class="text-sm text-danger" role="alert">{{ errorCajas }}</p>
      <div class="card overflow-x-auto">
        <table class="w-full">
          <thead><tr><th class="th">Caja</th><th class="th">Estado</th><th class="th"></th></tr></thead>
          <tbody>
            <tr v-for="c in cajas" :key="c.id" class="border-t border-slate-200 dark:border-slate-700">
              <td class="td">{{ c.nombre }}</td>
              <td class="td"><span :class="c.activa ? 'text-brand-600' : 'text-danger'">{{ c.activa ? 'Activa' : 'Inactiva' }}</span></td>
              <td class="td text-right"><button type="button" class="btn-ghost !px-2 !py-1 text-xs" @click="alternarCaja(c)">{{ c.activa ? 'Desactivar' : 'Activar' }}</button></td>
            </tr>
            <tr v-if="!cajas.length"><td class="td text-slate-500" colspan="3">Esta sucursal no tiene cajas.</td></tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- Modal usuario -->
    <Modal v-if="modalUsuario" :titulo="formUsuario.id ? 'Editar usuario' : 'Nuevo usuario'" ancho="max-w-2xl" @cerrar="modalUsuario = false">
      <form class="space-y-3" @submit.prevent="guardarUsuario">
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="text-sm"><span class="mb-1 block font-medium">Usuario *</span><input v-model="formUsuario.username" class="input" required maxlength="150" :disabled="formUsuario.id !== null" autocomplete="off" /></label>
          <label class="text-sm">
            <span class="mb-1 block font-medium">Contrasena{{ formUsuario.id ? ' (vacio = no cambiar)' : ' *' }}</span>
            <input v-model="formUsuario.password" class="input" type="password" :required="formUsuario.id === null" minlength="8" autocomplete="new-password" />
          </label>
          <label class="text-sm"><span class="mb-1 block font-medium">Nombre</span><input v-model="formUsuario.first_name" class="input" maxlength="150" /></label>
          <label class="text-sm"><span class="mb-1 block font-medium">Apellido</span><input v-model="formUsuario.last_name" class="input" maxlength="150" /></label>
          <label class="text-sm"><span class="mb-1 block font-medium">Correo</span><input v-model="formUsuario.email" class="input" type="email" /></label>
          <label class="text-sm"><span class="mb-1 block font-medium">CI</span><input v-model="formUsuario.ci" class="input" maxlength="20" /></label>
          <label class="text-sm"><span class="mb-1 block font-medium">Telefono</span><input v-model="formUsuario.telefono" class="input" maxlength="30" /></label>
          <label class="text-sm">
            <span class="mb-1 block font-medium">Rol *</span>
            <select v-model="formUsuario.rol" class="input" :disabled="esYo">
              <option v-for="r in ROLES" :key="r.id" :value="r.id">{{ r.texto }}</option>
            </select>
          </label>
        </div>

        <fieldset v-if="formUsuario.rol !== 'admin'" class="rounded-lg border border-slate-200 p-3 dark:border-slate-700">
          <legend class="px-1 text-sm font-medium">Sucursales donde opera</legend>
          <label v-for="s in sucursales.filter((x) => x.activa)" :key="s.id" class="mr-4 inline-flex items-center gap-2 text-sm">
            <input v-model="formUsuario.sucursales" type="checkbox" :value="s.id" /> {{ s.nombre }}
          </label>
        </fieldset>
        <p v-else class="text-xs text-slate-500">El administrador accede a todas las sucursales.</p>

        <label class="flex items-center gap-2 text-sm"><input v-model="formUsuario.is_active" type="checkbox" :disabled="esYo" /> Usuario activo</label>
        <p v-if="esYo" class="text-xs text-slate-500">No puedes cambiar tu propio rol ni desactivarte.</p>

        <p v-if="errorUsuario" class="text-sm text-danger" role="alert">{{ errorUsuario }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn-ghost" @click="modalUsuario = false">Cancelar</button>
          <button type="submit" class="btn-primary">Guardar</button>
        </div>
      </form>
    </Modal>

    <!-- Modal sucursal -->
    <Modal v-if="modalSucursal" :titulo="formSucursal.id ? 'Editar sucursal' : 'Nueva sucursal'" @cerrar="modalSucursal = false">
      <form class="space-y-3" @submit.prevent="guardarSucursal">
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="text-sm"><span class="mb-1 block font-medium">Codigo *</span><input v-model="formSucursal.codigo" class="input" required maxlength="10" /></label>
          <label class="text-sm"><span class="mb-1 block font-medium">Nombre *</span><input v-model="formSucursal.nombre" class="input" required maxlength="120" /></label>
          <label class="text-sm sm:col-span-2"><span class="mb-1 block font-medium">Direccion</span><input v-model="formSucursal.direccion" class="input" maxlength="255" /></label>
          <label class="text-sm"><span class="mb-1 block font-medium">Ciudad</span><input v-model="formSucursal.ciudad" class="input" maxlength="80" /></label>
          <label class="text-sm"><span class="mb-1 block font-medium">Telefono</span><input v-model="formSucursal.telefono" class="input" maxlength="30" /></label>
        </div>
        <div class="flex gap-4 text-sm">
          <label class="flex items-center gap-2"><input v-model="formSucursal.es_casa_matriz" type="checkbox" /> Casa matriz</label>
          <label class="flex items-center gap-2"><input v-model="formSucursal.activa" type="checkbox" /> Activa</label>
        </div>
        <p v-if="errorSucursal" class="text-sm text-danger" role="alert">{{ errorSucursal }}</p>
        <div class="flex justify-end gap-2">
          <button type="button" class="btn-ghost" @click="modalSucursal = false">Cancelar</button>
          <button type="submit" class="btn-primary">Guardar</button>
        </div>
      </form>
    </Modal>
  </section>
</template>
