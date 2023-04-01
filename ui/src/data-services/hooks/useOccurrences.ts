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
    { collection: 'occurrences', params },
    convertServerRecord
  )

  // This extra fetch is only until we have a real API
  const { data: examples, isLoading: examplesIsLoading } = useGetList<any, any>(
    { collection: 'examples' },
    (record: any) => record
  )

  return {
    occurrences: data.map((occurrence) => {
      if (examples.length) {
        occurrence.images = examples
          .filter((example) => example.sequence_id === occurrence.id)
          .map((example) => ({ src: example.cropped_image_path }))
      }
      return occurrence
    }),
    total: 16, // Hard coded until we get this in response
    isLoading: isLoading || examplesIsLoading,
  }
}
