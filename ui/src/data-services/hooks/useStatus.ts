import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { getFetchUrl } from 'data-services/utils'

type ServerStatus = any // TODO: Update this type

interface Status {
  numDeployments: number
  numCaptures: number
  numSessions: number
  numDetections: number
  numOccurrences: number
  numSpecies: number
}

const COLLECTION = 'status/summary'
const REFETCH_INTERVAL = undefined // TODO: Refetch every 10 second

const convertServerRecord = (record: ServerStatus): Status => ({
  numDeployments: record.num_deployments,
  numCaptures: record.num_captures,
  numSessions: record.num_sessions,
  numDetections: record.num_detections,
  numOccurrences: record.num_occurrences,
  numSpecies: record.num_species,
})

export const useStatus = (): {
  status?: Status
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: COLLECTION })

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: [COLLECTION],
    queryFn: () =>
      axios
        .get<ServerStatus>(fetchUrl)
        .then((res) => convertServerRecord(res.data)),
    refetchInterval: REFETCH_INTERVAL,
    retry: 0,
  })

  return {
    status: data,
    isLoading,
    isFetching,
    error,
  }
}
