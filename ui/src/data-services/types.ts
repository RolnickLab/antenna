export interface FetchParams {
  projectId?: string
  pagination?: { page: number; perPage: number }
  sort?: { field: string; order: 'asc' | 'desc' }
  filters?: { field: string; value?: string; error?: string }[]
  withCounts?: boolean
  withTrackStats?: boolean
}

export interface APIValidationError {
  detail: string
}
