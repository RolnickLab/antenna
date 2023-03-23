import { Occurrence, ServerOccurrence } from '../models/occurrence'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerOccurrence) => new Occurrence(record)

export const useOccurrences = (): {
  occurrences: Occurrence[]
  isLoading: boolean
} => {
  const { data, isLoading } = useGetList<ServerOccurrence, Occurrence>(
    'detections',
    convertServerRecord
  )

  return {
    occurrences: data,
    isLoading,
  }
}
