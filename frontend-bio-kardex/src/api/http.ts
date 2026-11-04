import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

export const TOKEN_KEYS = { access: 'bk-access', refresh: 'bk-refresh' } as const

export function leerToken(key: keyof typeof TOKEN_KEYS): string | null {
  try {
    return localStorage.getItem(TOKEN_KEYS[key])
  } catch {
    return null
  }
}

export function guardarTokens(access: string, refresh?: string) {
  try {
    localStorage.setItem(TOKEN_KEYS.access, access)
    if (refresh) localStorage.setItem(TOKEN_KEYS.refresh, refresh)
  } catch {
    /* ignorar */
  }
}

export function borrarTokens() {
  try {
    localStorage.removeItem(TOKEN_KEYS.access)
    localStorage.removeItem(TOKEN_KEYS.refresh)
  } catch {
    /* ignorar */
  }
}

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api',
})

http.interceptors.request.use((config) => {
  const token = leerToken('access')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Refresco automatico del access token (una sola peticion de refresh a la vez)
let refrescando: Promise<string> | null = null

async function refrescar(): Promise<string> {
  const refresh = leerToken('refresh')
  if (!refresh) throw new Error('sin refresh token')
  const { data } = await axios.post(`${http.defaults.baseURL}/auth/refresh/`, { refresh })
  guardarTokens(data.access, data.refresh)
  return data.access as string
}

type Reintentable = InternalAxiosRequestConfig & { _reintentada?: boolean }

http.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as Reintentable | undefined
    const esAuth =
      original?.url?.includes('/auth/login') || original?.url?.includes('/auth/refresh')
    if (error.response?.status === 401 && original && !original._reintentada && !esAuth) {
      original._reintentada = true
      try {
        refrescando ??= refrescar().finally(() => {
          refrescando = null
        })
        const nuevo = await refrescando
        original.headers.Authorization = `Bearer ${nuevo}`
        return http(original)
      } catch {
        borrarTokens()
        window.dispatchEvent(new Event('bk:sesion-expirada'))
      }
    }
    return Promise.reject(error)
  },
)
