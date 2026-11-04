export interface Paginado<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type Nivel = 'caja' | 'blister' | 'unidad'

export interface Presentacion {
  id: number
  producto: number
  nivel: Nivel
  nivel_display: string
  nombre: string
  factor: number
  precio: string
  codigo_barras: string | null
  activa: boolean
}

export interface Producto {
  id: number
  nombre_comercial: string
  principio_activo: number
  principio_activo_nombre: string
  concentracion: string
  forma: number
  forma_nombre: string
  laboratorio: string
  codigo_barras: string | null
  registro_sanitario: string
  es_controlado: boolean
  requiere_receta: boolean
  unidad_base: string
  stock_minimo: number
  imagen: string | null
  activo: boolean
  presentaciones: Presentacion[]
}

export interface Simple {
  id: number
  nombre: string
}

export type EstadoLote = 'ok' | 'por_vencer' | 'vencido' | 'bloqueado'

export interface StockItem {
  id: number
  sucursal: number
  lote_id: number
  numero_lote: string
  fecha_vencimiento: string
  producto_id: number
  producto: string
  cantidad: number
  bloqueado: boolean
  estado: EstadoLote
  dias_para_vencer: number
}

export interface Movimiento {
  id: number
  numero_lote: string
  producto: string
  tipo: string
  tipo_display: string
  cantidad: number
  saldo: number
  usuario_nombre: string
  motivo: string
  creado_en: string
}

export interface TraspasoItem {
  id: number
  lote: number
  numero_lote: string
  producto: string
  fecha_vencimiento: string
  cantidad_enviada: number
  cantidad_recibida: number | null
  diferencia: number | null
}

export interface Traspaso {
  id: number
  origen: number
  origen_nombre: string
  destino: number
  destino_nombre: string
  estado: 'enviado' | 'recibido' | 'rechazado'
  creado_por_nombre: string
  observacion: string
  observacion_recepcion: string
  creado_en: string
  items: TraspasoItem[]
}

export interface Caja {
  id: number
  sucursal: number
  nombre: string
  activa: boolean
}

export interface Turno {
  id: number
  caja: number
  caja_nombre: string
  cajero_nombre: string
  abierto_en: string
  cerrado_en: string | null
  abierto: boolean
  fondo_inicial: string
  efectivo_esperado: string | null
  qr_esperado: string | null
  efectivo_contado: string | null
  qr_contado: string | null
  diferencia_efectivo: string | null
  diferencia_qr: string | null
}

export interface TotalesTurno {
  fondo_inicial: string
  ventas_efectivo: string
  ventas_qr: string
  devoluciones_efectivo: string
  devoluciones_qr: string
  efectivo_esperado: string
  qr_esperado: string
}

export interface PosPresentacion {
  id: number
  nivel: Nivel
  nombre: string
  factor: number
  precio: string
  codigo_barras: string | null
  disponible: number
}

export interface PosProducto {
  id: number
  nombre: string
  concentracion: string
  forma: string
  principio_activo: string
  laboratorio: string
  imagen: string | null
  es_controlado: boolean
  requiere_receta: boolean
  unidad_base: string
  stock_base: number
  proximo_vencimiento: string | null
  presentaciones: PosPresentacion[]
}

export interface VentaLote {
  id: number
  numero_lote: string
  fecha_vencimiento: string
  cantidad_base: number
  devuelta: number
}

export interface VentaItem {
  id: number
  producto_nombre: string
  presentacion_nombre: string
  cantidad: number
  factor: number
  cantidad_base: number
  precio_unitario: string
  subtotal: string
  lotes: VentaLote[]
}

export interface Pago {
  id: number
  metodo: 'efectivo' | 'qr'
  metodo_display: string
  monto: string
  recibido: string
  vuelto: string
  referencia: string
  comprobante: string | null
}

export interface Venta {
  id: number
  numero: number
  sucursal_nombre: string
  cajero_nombre: string
  nombre_cliente: string
  documento_cliente: string
  subtotal: string
  descuento: string
  total: string
  iva: string
  vuelto: string
  estado: 'completada' | 'anulada'
  creado_en: string
  receta_numero: string
  medico: string
  motivo_anulacion: string
  items: VentaItem[]
  pagos: Pago[]
}

export interface VentaResumen {
  id: number
  numero: number
  cajero_nombre: string
  nombre_cliente: string
  total: string
  estado: 'completada' | 'anulada'
  creado_en: string
}
