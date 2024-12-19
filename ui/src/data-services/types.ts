export interface FetchParams {
  projectId?: string
  pagination?: { page: number; perPage: number }
  sort?: { field: string; order: 'asc' | 'desc' }
  filters?: { field: string; value?: string; isValid?: boolean }[]
}

export interface APIValidationError {
  detail: string
}
