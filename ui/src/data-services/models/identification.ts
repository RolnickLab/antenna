export interface ServerBulkIdentificationResult {
  index: number
  occurrence_id: number
  status: 'created' | 'error'
  id?: number
  errors?: Record<string, string[]>
}

export interface ServerBulkIdentificationResponse {
  created_count: number
  error_count: number
  results: ServerBulkIdentificationResult[]
}
