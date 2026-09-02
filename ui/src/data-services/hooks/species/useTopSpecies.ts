import { useSpecies } from './useSpecies'

export const useTopSpecies = (projectId: string) => {
  const result = useSpecies({
    pagination: { page: 0, perPage: 5 },
    projectId,
    sort: { field: 'occurrences_count', order: 'desc' },
  })

  return result
}
