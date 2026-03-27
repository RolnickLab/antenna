import { API_ROUTES, API_URL } from 'data-services/constants'
import { ServerTaxaList, TaxaList } from 'data-services/models/taxa-list'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerTaxaList) => new TaxaList(record)

export const useTaxaListDetails = (
  id: string,
  projectId: string
): {
  taxaList?: TaxaList
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } =
    useAuthorizedQuery<ServerTaxaList>({
      queryKey: [API_ROUTES.TAXA_LISTS, projectId, id],
      url: `${API_URL}/${API_ROUTES.TAXA_LISTS}/${id}/?project_id=${projectId}`,
    })

  const taxaList = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    taxaList,
    isLoading,
    isFetching,
    error,
  }
}
