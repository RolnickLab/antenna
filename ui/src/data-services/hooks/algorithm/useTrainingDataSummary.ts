import { API_ROUTES, API_URL } from 'data-services/constants'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

export interface ServerTrainingDataSummary {
  rows: number
  classes: number
  train: number
  test: number
  verified_detections_without_embedding: number
}

export interface TrainingDataSummary {
  cropsReady: number
  species: number
  cropsWithoutEmbedding: number
}

const convertServerRecord = (
  record: ServerTrainingDataSummary
): TrainingDataSummary => ({
  cropsReady: record.rows,
  species: record.classes,
  cropsWithoutEmbedding: record.verified_detections_without_embedding,
})

export const useTrainingDataSummary = (
  projectId?: string,
  algorithmKey?: string
): {
  summary?: TrainingDataSummary
  isLoading: boolean
  error?: unknown
} => {
  const params = { project_id: projectId ?? '', algorithm: algorithmKey ?? '' }
  const queryString = new URLSearchParams(params).toString()

  const { data, isLoading, error } =
    useAuthorizedQuery<ServerTrainingDataSummary>({
      queryKey: [API_ROUTES.TRAINING_DATA, params],
      url: `${API_URL}/${API_ROUTES.TRAINING_DATA}/summary/?${queryString}`,
      enabled: !!projectId && !!algorithmKey,
    })

  return {
    summary: data ? convertServerRecord(data) : undefined,
    isLoading,
    error,
  }
}
