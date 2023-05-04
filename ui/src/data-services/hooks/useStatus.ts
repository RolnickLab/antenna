import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'

type ServerStatus = any // TODO: Update this type

interface Status {
  numDeployments: number
  numCaptures: number
  numSessions: number
  numDetections: number
  numOccurrences: number
  numSpecies: number
}

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
  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ['status'],
    queryFn: () =>
      axios
        .get<ServerStatus>(`${API_URL}/status/summary`)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    status: data,
    isLoading,
    isFetching,
    error,
  }
}
