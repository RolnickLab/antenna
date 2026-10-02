export interface FetchParams {
  projectId?: string
  pagination?: { page: number; perPage: number }
  sort?: { field: string; order: 'asc' | 'desc' }
  filters?: { field: string; value?: string; error?: string }[]
  withCounts?: boolean
  withExampleOccurrences?: boolean
  withPeakCounts?: boolean
}

export interface APIValidationError {
  detail: string
}
