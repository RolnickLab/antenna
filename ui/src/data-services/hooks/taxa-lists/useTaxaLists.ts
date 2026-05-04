import { API_ROUTES } from 'data-services/constants'
import { ServerTaxaList, TaxaList } from 'data-services/models/taxa-list'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

// Convert server response to a TaxaList instance
const convertServerRecord = (record: ServerTaxaList) => new TaxaList(record)

export const useTaxaLists = (
  params?: FetchParams
): {
  taxaLists?: TaxaList[]
  total: number
  userPermissions?: UserPermission[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  // Construct API fetch URL with query parameters
  const fetchUrl = getFetchUrl({
    collection: API_ROUTES.TAXA_LISTS,
    params,
  })

  // Fetch data from API
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    count: number
    results: ServerTaxaList[]
    user_permissions?: UserPermission[]
  }>({
    queryKey: [API_ROUTES.TAXA_LISTS, params],
    url: fetchUrl,
  })

  // Convert raw server response into TaxaList instances
  const taxaLists = useMemo(
    () => data?.results.map(convertServerRecord),
    [data]
  )

  return {
    taxaLists,
    total: data?.count ?? 0,
    userPermissions: data?.user_permissions,
    isLoading,
    isFetching,
    error,
  }
}
