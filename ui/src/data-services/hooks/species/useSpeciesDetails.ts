import { API_ROUTES, API_URL } from 'data-services/constants'

import {
  ServerSpeciesDetails,
  SpeciesDetails,
} from 'data-services/models/species-details'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerSpeciesDetails) =>
  new SpeciesDetails(record)

export const useSpeciesDetails = (
  id: string,
  projectId: string | undefined,
): {
  species?: SpeciesDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<SpeciesDetails>({
      queryKey: [API_ROUTES.SPECIES, id],
      url: `${API_URL}/${API_ROUTES.SPECIES}/${id}/?project=${projectId || ''}`,
    })

  const species = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    species,
    isLoading,
    isFetching,
    error,
  }
}
