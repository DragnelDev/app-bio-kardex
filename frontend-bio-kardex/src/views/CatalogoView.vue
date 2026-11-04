<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { http } from '@/api/http'
import Modal from '@/components/Modal.vue'
import { mensajeError } from '@/utils/errores'
import { bs } from '@/utils/format'
import type { Nivel, Paginado, Presentacion, Producto, Simple } from '@/types'

const productos = ref<Producto[]>([])
const total = ref(0)
const pagina = ref(1)
const q = ref('')
const soloActivos = ref(true)
const error = ref('')

const principios = ref<Simple[]>([])
const formas = ref<Simple[]>([])

const abierto = ref(false)
const editando = ref<Producto | null>(null)
const guardando = ref(false)
const errorForm = ref('')
const archivo = ref<File | null>(null)

const form = reactive({
  nombre_comercial: '',
  principio_activo: null as number | null,
  concentracion: '',
  forma: null as number | null,
  laboratorio: '',
  codigo_barras: '',
  registro_sanitario: '',
  es_controlado: false,
  requiere_receta: false,
  unidad_base: 'unidad',
  stock_minimo: 0,
  activo: true,
})

interface FilaPres {
  id: number | null
  nivel: Nivel
  nombre: string
  factor: number
  precio: string
  codigo_barras: string
  activa: boolean
  error: string
  guardada: boolean
}
const filas = ref<FilaPres[]>([])

let temporizador: ReturnType<typeof setTimeout> | undefined
watch([q, soloActivos], () => {
  clearTimeout(temporizador)
  temporizador = setTimeout(() => cargar(1), 300)
})

async function cargar(p = 1) {
  pagina.value = p
  error.value = ''
  try {
    const { data } = await http.get<Paginado<Producto>>('/productos/', {
      params: {
        q: q.value || undefined,
        activo: soloActivos.value ? 1 : undefined,
        page: p,
        page_size: 20,
      },
    })
    productos.value = data.results
    total.value = data.count
  } catch (e) {
    error.value = mensajeError(e)
  }
}

async function cargarListas() {
  const [a, b] = await Promise.all([
    http.get<Paginado<Simple>>('/principios-activos/', { params: { page_size: 200 } }),
    http.get<Paginado<Simple>>('/formas-farmaceuticas/', { params: { page_size: 200 } }),
  ])
  principios.value = a.data.results
  formas.value = b.data.results
}

async function crearLista(tipo: 'principios-activos' | 'formas-farmaceuticas') {
  const nombre = window.prompt('Nombre:')?.trim()
  if (!nombre) return
  try {
    const { data } = await http.post<Simple>(`/${tipo}/`, { nombre })
    if (tipo === 'principios-activos') {
      principios.value.push(data)
      form.principio_activo = data.id
    } else {
      formas.value.push(data)
      form.forma = data.id
    }
  } catch (e) {
    errorForm.value = mensajeError(e)
  }
}

function cargarFilas(p: Producto | null) {
  filas.value = (p?.presentaciones ?? []).map((x: Presentacion) => ({
    id: x.id,
    nivel: x.nivel,
    nombre: x.nombre,
    factor: x.factor,
    precio: x.precio,
    codigo_barras: x.codigo_barras ?? '',
    activa: x.activa,
    error: '',
    guardada: true,
  }))
}

function nuevo() {
  editando.value = null
  archivo.value = null
  errorForm.value = ''
  Object.assign(form, {
    nombre_comercial: '',
    principio_activo: null,
    concentracion: '',
    forma: null,
    laboratorio: '',
    codigo_barras: '',
    registro_sanitario: '',
    es_controlado: false,
    requiere_receta: false,
    unidad_base: 'unidad',
    stock_minimo: 0,
    activo: true,
  })
  cargarFilas(null)
  abierto.value = true
}

function editar(p: Producto) {
  editando.value = p
  archivo.value = null
  errorForm.value = ''
  Object.assign(form, {
    nombre_comercial: p.nombre_comercial,
    principio_activo: p.principio_activo,
    concentracion: p.concentracion,
    forma: p.forma,
    laboratorio: p.laboratorio,
    codigo_barras: p.codigo_barras ?? '',
    registro_sanitario: p.registro_sanitario,
    es_controlado: p.es_controlado,
    requiere_receta: p.requiere_receta,
    unidad_base: p.unidad_base,
    stock_minimo: p.stock_minimo,
    activo: p.activo,
  })
  cargarFilas(p)
  abierto.value = true
}

function alElegirImagen(e: Event) {
  archivo.value = (e.target as HTMLInputElement).files?.[0] ?? null
}

async function guardarProducto() {
  errorForm.value = ''
  guardando.value = true
  try {
    const datos = new FormData()
    for (const [k, v] of Object.entries(form)) {
      if (v === null) continue
      if (k === 'codigo_barras' && v === '') continue
      datos.append(k, String(v))
    }
    if (archivo.value) datos.append('imagen', archivo.value)
    const { data } = editando.value
      ? await http.patch<Producto>(`/productos/${editando.value.id}/`, datos)
      : await http.post<Producto>('/productos/', datos)
    editando.value = data
    cargarFilas(data)
    await cargar(pagina.value)
  } catch (e) {
    errorForm.value = mensajeError(e)
  } finally {
    guardando.value = false
  }
}

function agregarFila() {
  const usados = new Set(filas.value.map((f) => f.nivel))
  const libre = (['caja', 'blister', 'unidad'] as Nivel[]).find((n) => !usados.has(n))
  if (!libre) return
  filas.value.push({
    id: null,
    nivel: libre,
    nombre: '',
    factor: libre === 'unidad' ? 1 : 10,
    precio: '0.00',
    codigo_barras: '',
    activa: true,
    error: '',
    guardada: false,
  })
}

async function guardarFila(f: FilaPres) {
  if (!editando.value) return
  f.error = ''
  const cuerpo = {
    producto: editando.value.id,
    nivel: f.nivel,
    nombre: f.nombre,
    factor: f.nivel === 'unidad' ? 1 : f.factor,
    precio: Number(f.precio).toFixed(2),
    codigo_barras: f.codigo_barras || null,
    activa: f.activa,
  }
  try {
    const { data } = f.id
      ? await http.patch<Presentacion>(`/presentaciones/${f.id}/`, cuerpo)
      : await http.post<Presentacion>('/presentaciones/', cuerpo)
    f.id = data.id
    f.factor = data.factor
    f.guardada = true
    await cargar(pagina.value)
  } catch (e) {
    f.error = mensajeError(e)
  }
}

function resumenPres(p: Producto) {
  return p.presentaciones
    .filter((x) => x.activa)
    .map((x) => `${x.nivel_display} x${x.factor} ${bs(x.precio)}`)
    .join(' · ')
}

onMounted(() => {
  cargar()
  cargarListas()
})
</script>

<template>
  <section class="space-y-4">
    <div class="flex flex-wrap items-center gap-3">
      <h1 class="text-2xl font-semibold">Catalogo</h1>
      <input
        v-model="q"
        class="input !w-64"
        type="search"
        placeholder="Buscar producto, principio activo o codigo"
      />
      <label class="flex items-center gap-2 text-sm"
        ><input v-model="soloActivos" type="checkbox" /> Solo activos</label
      >
      <button type="button" class="btn-primary ml-auto" @click="nuevo">
        <i class="pi pi-plus" aria-hidden="true"></i> Nuevo producto
      </button>
    </div>
    <p v-if="error" class="text-sm text-danger" role="alert">{{ error }}</p>

    <div class="card overflow-x-auto">
      <table class="w-full">
        <thead>
          <tr>
            <th class="th"></th>
            <th class="th">Producto</th>
            <th class="th">Principio activo</th>
            <th class="th">Presentaciones</th>
            <th class="th">Estado</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="p in productos"
            :key="p.id"
            class="cursor-pointer border-t border-slate-200 hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-700/40"
            @click="editar(p)"
          >
            <td class="td w-14">
              <div
                class="flex h-10 w-10 items-center justify-center overflow-hidden rounded bg-slate-100 dark:bg-slate-700"
              >
                <img
                  v-if="p.imagen"
                  :src="p.imagen"
                  :alt="p.nombre_comercial"
                  class="h-full w-full object-cover"
                />
                <i v-else class="pi pi-image text-slate-400" aria-hidden="true"></i>
              </div>
            </td>
            <td class="td font-medium">
              {{ p.nombre_comercial }}
              <span class="font-normal text-slate-500"
                >{{ p.concentracion }} · {{ p.forma_nombre }}</span
              >
              <span v-if="p.es_controlado" class="ml-1 rounded bg-warn/20 px-1.5 text-xs"
                >controlado</span
              >
            </td>
            <td class="td">{{ p.principio_activo_nombre }}</td>
            <td class="td text-xs text-slate-500">{{ resumenPres(p) || 'Sin presentaciones' }}</td>
            <td class="td">{{ p.activo ? 'Activo' : 'Inactivo' }}</td>
          </tr>
          <tr v-if="!productos.length">
            <td class="td text-slate-500" colspan="5">Sin productos.</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="total > 20" class="flex items-center justify-between text-sm">
      <button class="btn-ghost" :disabled="pagina <= 1" @click="cargar(pagina - 1)">
        Anterior
      </button>
      <span>Pagina {{ pagina }} · {{ total }} productos</span>
      <button class="btn-ghost" :disabled="pagina * 20 >= total" @click="cargar(pagina + 1)">
        Siguiente
      </button>
    </div>

    <Modal
      v-if="abierto"
      :titulo="editando ? 'Editar producto' : 'Nuevo producto'"
      ancho="max-w-3xl"
      @cerrar="abierto = false"
    >
      <form class="space-y-3" @submit.prevent="guardarProducto">
        <div class="grid gap-3 sm:grid-cols-2">
          <label class="text-sm sm:col-span-2"
            ><span class="mb-1 block font-medium">Nombre comercial *</span
            ><input v-model="form.nombre_comercial" class="input" required maxlength="200"
          /></label>
          <label class="text-sm">
            <span class="mb-1 block font-medium">Principio activo *</span>
            <span class="flex gap-1">
              <select v-model="form.principio_activo" class="input" required>
                <option :value="null" disabled>Elegir...</option>
                <option v-for="x in principios" :key="x.id" :value="x.id">{{ x.nombre }}</option>
              </select>
              <button
                type="button"
                class="btn-ghost"
                title="Nuevo principio activo"
                @click="crearLista('principios-activos')"
              >
                +
              </button>
            </span>
          </label>
          <label class="text-sm">
            <span class="mb-1 block font-medium">Forma farmaceutica *</span>
            <span class="flex gap-1">
              <select v-model="form.forma" class="input" required>
                <option :value="null" disabled>Elegir...</option>
                <option v-for="x in formas" :key="x.id" :value="x.id">{{ x.nombre }}</option>
              </select>
              <button
                type="button"
                class="btn-ghost"
                title="Nueva forma"
                @click="crearLista('formas-farmaceuticas')"
              >
                +
              </button>
            </span>
          </label>
          <label class="text-sm"
            ><span class="mb-1 block font-medium">Concentracion</span
            ><input v-model="form.concentracion" class="input" maxlength="80" placeholder="500 mg"
          /></label>
          <label class="text-sm"
            ><span class="mb-1 block font-medium">Laboratorio</span
            ><input v-model="form.laboratorio" class="input" maxlength="120"
          /></label>
          <label class="text-sm"
            ><span class="mb-1 block font-medium">Codigo de barras</span
            ><input v-model="form.codigo_barras" class="input" maxlength="60"
          /></label>
          <label class="text-sm"
            ><span class="mb-1 block font-medium">Registro sanitario</span
            ><input v-model="form.registro_sanitario" class="input" maxlength="60"
          /></label>
          <label class="text-sm"
            ><span class="mb-1 block font-medium">Unidad base (tableta, ml...)</span
            ><input v-model="form.unidad_base" class="input" maxlength="30" required
          /></label>
          <label class="text-sm"
            ><span class="mb-1 block font-medium">Stock minimo (unidades base)</span
            ><input v-model.number="form.stock_minimo" class="input" type="number" min="0"
          /></label>
          <label class="text-sm sm:col-span-2">
            <span class="mb-1 block font-medium">Imagen</span>
            <input class="input" type="file" accept="image/*" @change="alElegirImagen" />
            <img
              v-if="editando?.imagen && !archivo"
              :src="editando.imagen"
              alt="Imagen actual"
              class="mt-2 h-20 rounded"
            />
          </label>
        </div>
        <div class="flex flex-wrap gap-4 text-sm">
          <label class="flex items-center gap-2"
            ><input v-model="form.es_controlado" type="checkbox" /> Controlado (psicotropico /
            estupefaciente)</label
          >
          <label class="flex items-center gap-2"
            ><input v-model="form.requiere_receta" type="checkbox" /> Requiere receta</label
          >
          <label class="flex items-center gap-2"
            ><input v-model="form.activo" type="checkbox" /> Activo</label
          >
        </div>
        <p v-if="errorForm" class="text-sm text-danger" role="alert">{{ errorForm }}</p>
        <div class="flex justify-end">
          <button type="submit" class="btn-primary" :disabled="guardando">
            {{ editando ? 'Guardar cambios' : 'Crear producto' }}
          </button>
        </div>
      </form>

      <div
        v-if="editando"
        class="mt-5 space-y-2 border-t border-slate-200 pt-4 dark:border-slate-700"
      >
        <div class="flex items-center justify-between">
          <h3 class="font-semibold">Presentaciones y precios (con IVA)</h3>
          <button v-if="filas.length < 3" type="button" class="btn-ghost" @click="agregarFila">
            + Agregar nivel
          </button>
        </div>
        <p class="text-xs text-slate-500">
          El factor es cuantas unidades base contiene el nivel (caja x30 = 30). El stock se maneja
          siempre en unidades base.
        </p>
        <div
          v-for="f in filas"
          :key="f.nivel"
          class="grid grid-cols-2 items-end gap-2 rounded-lg border border-slate-200 p-2 text-sm dark:border-slate-700 sm:grid-cols-7"
        >
          <label
            ><span class="block text-xs text-slate-500">Nivel</span
            ><select v-model="f.nivel" class="input" disabled>
              <option value="caja">Caja</option>
              <option value="blister">Blister</option>
              <option value="unidad">Unidad</option>
            </select></label
          >
          <label
            ><span class="block text-xs text-slate-500">Nombre</span
            ><input v-model="f.nombre" class="input" maxlength="80" placeholder="Caja x 30"
          /></label>
          <label
            ><span class="block text-xs text-slate-500">Factor</span
            ><input
              v-model.number="f.factor"
              class="input"
              type="number"
              min="1"
              :disabled="f.nivel === 'unidad'"
          /></label>
          <label
            ><span class="block text-xs text-slate-500">Precio (Bs)</span
            ><input v-model="f.precio" class="input" type="number" min="0" step="0.01"
          /></label>
          <label
            ><span class="block text-xs text-slate-500">Cod. barras</span
            ><input v-model="f.codigo_barras" class="input" maxlength="60"
          /></label>
          <label class="flex items-center gap-1"
            ><input v-model="f.activa" type="checkbox" /> Activa</label
          >
          <button type="button" class="btn-primary" @click="guardarFila(f)">
            {{ f.guardada ? 'Actualizar' : 'Guardar' }}
          </button>
          <p v-if="f.error" class="col-span-full text-xs text-danger">{{ f.error }}</p>
        </div>
      </div>
    </Modal>
  </section>
</template>
