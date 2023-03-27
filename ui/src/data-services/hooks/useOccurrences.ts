import { FetchSettings } from 'data-services/types'
import { Occurrence, ServerOccurrence } from '../models/occurrence'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerOccurrence) => new Occurrence(record)

export const useOccurrences = (
  settings?: FetchSettings
): {
  occurrences: Occurrence[]
  isLoading: boolean
} => {
  const { data, isLoading } = useGetList<ServerOccurrence, Occurrence>(
    { collection: 'detections', settings },
    convertServerRecord
  )

  return {
    occurrences: data,
    isLoading,
  }
}
