import { API_ROUTES } from 'data-services/constants'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { useAuthorizedQuery } from './auth/useAuthorizedQuery'

type ServerStatus = any // TODO: Update this type

interface Status {
  numDeployments: number
  numCaptures: number
  numSessions: number
  numDetections: number
  numOccurrences: number
  numSpecies: number
}

const REFETCH_INTERVAL = 10000 // Refetch every 10 second

const convertServerRecord = (record: ServerStatus): Status => ({
  numDeployments: record.num_deployments,
  numCaptures: record.num_captures,
  numSessions: record.num_sessions,
  numDetections: record.num_detections,
  numOccurrences: record.num_occurrences,
  numSpecies: record.num_species,
})

export const useStatus = (
  projectId?: string
): {
  status?: Status
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const params = { projectId }

  const fetchUrl = getFetchUrl({
    collection: API_ROUTES.SUMMARY,
    params,
  })

  const { data, isLoading, error, isFetching } =
    useAuthorizedQuery<ServerStatus>({
      queryKey: [API_ROUTES.SUMMARY, params],
      url: fetchUrl,
      refetchInterval: REFETCH_INTERVAL,
    })

  const status = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    status,
    isLoading,
    isFetching,
    error,
  }
}
