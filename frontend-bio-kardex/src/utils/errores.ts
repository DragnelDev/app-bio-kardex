import { isAxiosError } from 'axios'

/** Convierte un error de axios/DRF en un mensaje legible en espanol. */
export function mensajeError(e: unknown): string {
  if (isAxiosError(e)) {
    if (!e.response) return 'Sin conexion con el servidor.'
    const d = e.response.data as unknown
    if (d && typeof d === 'object') {
      const obj = d as Record<string, unknown>
      if (typeof obj.detail === 'string') return obj.detail
      const partes = Object.entries(obj).map(([k, v]) => {
        const texto = Array.isArray(v) ? v.join(' ') : String(v)
        return k === 'non_field_errors' ? texto : `${k}: ${texto}`
      })
      if (partes.length) return partes.join(' · ')
    }
    if (e.response.status === 403) return 'No tienes permiso para esta accion.'
  }
  return 'Ocurrio un error inesperado.'
}
