export interface FetchParams {
  projectId?: string
  pagination?: { page: number; perPage: number }
  sort?: { field: string; order: 'asc' | 'desc' }
  filters?: { field: string; value?: string; error?: string }[]
}

export interface APIValidationError {
  detail: string
}
