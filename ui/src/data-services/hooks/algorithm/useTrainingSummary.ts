import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const COLLECTION = 'ml/training-data/summary'

type ServerTrainingSummary = any // TODO: Update this type

interface TrainingSummary {
  numClasses: number
  numOccurrences: number
  numRows: number
  numTest: number
  numTrain: number
  numWithoutEmbedding: number
}

const convertServerRecord = (
  record: ServerTrainingSummary
): TrainingSummary => ({
  numClasses: record.trainable_classes,
  numOccurrences: record.occurrences,
  numRows: record.rows,
  numTest: record.test,
  numTrain: record.train,
  numWithoutEmbedding: record.verified_detections_without_embedding,
})

export const useTrainingSummary = ({
  algorithm,
  minPerSpecies,
  occurrenceSet,
  projectId,
  testFraction,
}: {
  algorithm?: string
  minPerSpecies?: number
  occurrenceSet?: string
  projectId?: string
  testFraction?: number
}): {
  summary?: TrainingSummary
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  // Settings are sent only when set, so the server answers with the algorithm's own.
  const params: FetchParams = {
    projectId,
    filters: [
      { field: 'algorithm', value: algorithm },
      { field: 'occurrence_set', value: occurrenceSet },
      {
        field: 'test_fraction',
        value: testFraction !== undefined ? `${testFraction}` : undefined,
      },
      {
        field: 'min_per_species',
        value: minPerSpecies !== undefined ? `${minPerSpecies}` : undefined,
      },
    ],
  }

  const fetchUrl = getFetchUrl({ collection: COLLECTION, params })

  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ServerTrainingSummary>({
      enabled: !!projectId && !!algorithm,
      queryKey: [COLLECTION, params],
      url: fetchUrl,
    })

  const summary = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    summary,
    isLoading,
    isFetching,
    error,
  }
}
