import { API_ROUTES } from 'data-services/constants'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { ServerSpecies, Species } from '../../models/species'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerSpecies) => new Species(record)

export const useSpecies = (
  params?: FetchParams
): {
  species?: Species[]
  userPermissions?: UserPermission[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: API_ROUTES.SPECIES, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerSpecies[]
    count: number
    user_permissions?: UserPermission[]
  }>({
    queryKey: [API_ROUTES.SPECIES, params],
    url: fetchUrl,
  })

  const species = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    species,
    userPermissions: data?.user_permissions,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
