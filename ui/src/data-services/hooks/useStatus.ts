import { useGetListItem } from './useGetListItem'

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
  error?: string
} => {
  const { data, isLoading, error } = useGetListItem<any, any>(
    { collection: 'status', id: 'summary' },
    convertServerRecord
  )

  return {
    status: data,
    isLoading,
    error,
  }
}
