import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { Nivel, PosPresentacion, PosProducto } from '@/types'
import { redondear } from '@/utils/format'

export interface LineaCarrito {
  presentacionId: number
  productoId: number
  nombre: string
  presentacion: string
  nivel: Nivel
  factor: number
  precio: number
  cantidad: number
  imagen: string | null
  /** Unidades base disponibles del producto al momento de agregarlo */
  stockBase: number
  esControlado: boolean
  requiereReceta: boolean
}

function uuid(): string {
  // randomUUID solo existe en contextos seguros (https o localhost)
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16)
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16)
  })
}

export const usePosStore = defineStore('pos', () => {
  const lineas = ref<LineaCarrito[]>([])
  const descuento = ref(0)
  const clienteDocumento = ref('')
  const clienteNombre = ref('')
  const recetaNumero = ref('')
  const medico = ref('')
  /** Identificador de idempotencia: un reintento de la misma venta no la duplica. */
  const referencia = ref(uuid())

  const subtotal = computed(() =>
    redondear(lineas.value.reduce((t, l) => t + redondear(l.precio * l.cantidad), 0)),
  )
  const total = computed(() => redondear(Math.max(0, subtotal.value - descuento.value)))
  const cantidadItems = computed(() => lineas.value.reduce((t, l) => t + l.cantidad, 0))
  const requiereReceta = computed(() =>
    lineas.value.some((l) => l.requiereReceta || l.esControlado),
  )
  const esControlado = computed(() => lineas.value.some((l) => l.esControlado))

  /** Unidades base pedidas de un producto sumando todas sus presentaciones en el carrito. */
  function baseSolicitada(productoId: number): number {
    return lineas.value
      .filter((l) => l.productoId === productoId)
      .reduce((t, l) => t + l.cantidad * l.factor, 0)
  }

  function excedeStock(l: LineaCarrito): boolean {
    return baseSolicitada(l.productoId) > l.stockBase
  }
  const hayExcesoDeStock = computed(() => lineas.value.some(excedeStock))

  function agregar(producto: PosProducto, p: PosPresentacion) {
    const existente = lineas.value.find((l) => l.presentacionId === p.id)
    if (existente) {
      existente.cantidad++
      existente.stockBase = producto.stock_base
      return
    }
    lineas.value.push({
      presentacionId: p.id,
      productoId: producto.id,
      nombre: `${producto.nombre} ${producto.concentracion}`.trim(),
      presentacion: p.nombre,
      nivel: p.nivel,
      factor: p.factor,
      precio: Number(p.precio),
      cantidad: 1,
      imagen: producto.imagen,
      stockBase: producto.stock_base,
      esControlado: producto.es_controlado,
      requiereReceta: producto.requiere_receta,
    })
  }

  function cambiarCantidad(presentacionId: number, cantidad: number) {
    const l = lineas.value.find((x) => x.presentacionId === presentacionId)
    if (!l) return
    if (!Number.isFinite(cantidad) || cantidad < 1) cantidad = 1
    l.cantidad = Math.floor(cantidad)
  }

  function quitar(presentacionId: number) {
    lineas.value = lineas.value.filter((l) => l.presentacionId !== presentacionId)
  }

  function vaciar() {
    lineas.value = []
    descuento.value = 0
    clienteDocumento.value = ''
    clienteNombre.value = ''
    recetaNumero.value = ''
    medico.value = ''
    referencia.value = uuid()
  }

  return {
    lineas,
    descuento,
    clienteDocumento,
    clienteNombre,
    recetaNumero,
    medico,
    referencia,
    subtotal,
    total,
    cantidadItems,
    requiereReceta,
    esControlado,
    hayExcesoDeStock,
    baseSolicitada,
    excedeStock,
    agregar,
    cambiarCantidad,
    quitar,
    vaciar,
  }
})
