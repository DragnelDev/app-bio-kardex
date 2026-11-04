import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { usePosStore } from '../pos'
import type { PosProducto } from '@/types'

const producto: PosProducto = {
  id: 1,
  nombre: 'Paracetamol',
  concentracion: '500 mg',
  forma: 'Tableta',
  principio_activo: 'Paracetamol',
  laboratorio: '',
  imagen: null,
  es_controlado: false,
  requiere_receta: false,
  unidad_base: 'tableta',
  stock_base: 100,
  proximo_vencimiento: null,
  presentaciones: [
    {
      id: 10,
      nivel: 'caja',
      nombre: 'Caja x30',
      factor: 30,
      precio: '24.00',
      codigo_barras: null,
      disponible: 3,
    },
    {
      id: 11,
      nivel: 'unidad',
      nombre: 'Unidad',
      factor: 1,
      precio: '1.00',
      codigo_barras: null,
      disponible: 100,
    },
  ],
}

describe('carrito del POS', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('suma cantidades al agregar la misma presentacion', () => {
    const pos = usePosStore()
    const caja = producto.presentaciones[0]!
    pos.agregar(producto, caja)
    pos.agregar(producto, caja)
    expect(pos.lineas).toHaveLength(1)
    expect(pos.lineas[0]!.cantidad).toBe(2)
    expect(pos.total).toBe(48)
  })

  it('aplica descuento y no baja de cero', () => {
    const pos = usePosStore()
    pos.agregar(producto, producto.presentaciones[0]!)
    pos.descuento = 4
    expect(pos.total).toBe(20)
    pos.descuento = 999
    expect(pos.total).toBe(0)
  })

  it('detecta exceso de stock sumando todas las presentaciones del producto', () => {
    const pos = usePosStore()
    pos.agregar(producto, producto.presentaciones[0]!) // 30
    pos.cambiarCantidad(10, 3) // 90
    expect(pos.hayExcesoDeStock).toBe(false)
    pos.agregar(producto, producto.presentaciones[1]!) // +1 = 91
    pos.cambiarCantidad(11, 11) // 90 + 11 = 101 > 100
    expect(pos.hayExcesoDeStock).toBe(true)
  })

  it('vaciar reinicia el carrito y genera una nueva referencia', () => {
    const pos = usePosStore()
    const anterior = pos.referencia
    pos.agregar(producto, producto.presentaciones[0]!)
    pos.vaciar()
    expect(pos.lineas).toHaveLength(0)
    expect(pos.referencia).not.toBe(anterior)
  })
})
