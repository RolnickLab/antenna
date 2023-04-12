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
  error?: string
} => {
  const {
    data: occurrences,
    isLoading,
    error,
  } = useGetList<ServerOccurrence, Occurrence>(
    { collection: 'occurrences', params },
    convertServerRecord
  )

  return {
    occurrences,
    total: occurrences.length, // TODO: Until we get total in response
    isLoading,
    error,
  }
}
