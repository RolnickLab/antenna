import { useOccurrences } from './useOccurrences'

export const useLatestOccurrences = (projectId: string) => {
  const result = useOccurrences({
    pagination: { page: 0, perPage: 5 },
    projectId,
    sort: { field: 'first_appearance_timestamp', order: 'desc' },
  })

  return result
}
