const monedaFmt = new Intl.NumberFormat('es-BO', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** Formato de Bolivianos: "Bs 1.234,50". Acepta numero o string decimal del API. */
export function bs(valor: number | string | null | undefined): string {
  if (valor === null || valor === undefined || valor === '') return '—'
  return `Bs ${monedaFmt.format(Number(valor))}`
}

export function redondear(n: number): number {
  return Math.round((n + Number.EPSILON) * 100) / 100
}

export function fecha(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${y}`
}

export function fechaHora(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-BO', { hour12: false })
}

export function hoyISO(): string {
  const d = new Date()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dia = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${dia}`
}

/** Convierte unidades base a texto por niveles: 125 -> "4 cajas + 5 u." */
export function base(cantidad: number, factorCaja?: number, unidad = 'u.'): string {
  if (!factorCaja || factorCaja <= 1) return `${cantidad} ${unidad}`
  const cajas = Math.floor(cantidad / factorCaja)
  const resto = cantidad % factorCaja
  if (cajas === 0) return `${resto} ${unidad}`
  return resto === 0 ? `${cajas} cj.` : `${cajas} cj. + ${resto} ${unidad}`
}
