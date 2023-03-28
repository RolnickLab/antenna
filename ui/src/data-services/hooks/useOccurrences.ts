import { FetchParams } from 'data-services/types'
import { Occurrence, ServerOccurrence } from '../models/occurrence'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerOccurrence) => new Occurrence(record)

export const useOccurrences = (
  params?: FetchParams
): {
  occurrences: Occurrence[]
  total: number
  isLoading: boolean
} => {
  const { data, isLoading } = useGetList<ServerOccurrence, Occurrence>(
    { collection: 'detections', params },
    convertServerRecord
  )

  return {
    occurrences: data,
    total: 10, // Hard coded until we get this in response
    isLoading,
  }
}
