import axios, { AxiosError, type AxiosInstance } from 'axios'

/**
 * Envelope de erro do backend (Seção 5.5 do plano F2):
 *   { error: { code, message, detail? } }
 */
export interface ApiErrorShape {
  error: {
    code: string
    message: string
    detail?: Record<string, unknown>
  }
}

export class ApiError extends Error {
  public readonly code: string
  public readonly status: number
  public readonly detail?: Record<string, unknown>

  constructor(code: string, message: string, status: number, detail?: Record<string, unknown>) {
    super(message)
    this.code = code
    this.status = status
    this.detail = detail
    this.name = 'ApiError'
  }
}

/** Base path para o backend. Vite proxy cuida do redirect em dev. */
export const API_BASE_URL = '/api/v1'

/** Axios client configurado com interceptors padronizados. */
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorShape>) => {
    // Axios/network-level errors (sem response) viram ApiError tipo network
    if (!error.response) {
      return Promise.reject(
        new ApiError(
          'network_error',
          error.message || 'Falha de rede ao chamar a API.',
          0,
        ),
      )
    }

    const { status, data } = error.response
    if (data && typeof data === 'object' && 'error' in data) {
      const e = data.error
      return Promise.reject(
        new ApiError(
          e.code ?? `http_${status}`,
          e.message ?? 'Erro desconhecido.',
          status,
          e.detail,
        ),
      )
    }

    // Fallback: resposta de erro sem envelope padrão
    return Promise.reject(
      new ApiError(
        `http_${status}`,
        error.message || `Erro HTTP ${status}`,
        status,
      ),
    )
  },
)
