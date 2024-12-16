import { API_ROUTES, API_URL } from 'data-services/constants'
import { Collection, ServerCollection } from 'data-services/models/collection'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerCollection) => new Collection(record)

export const useCollectionDetails = (
  id: string
): {
  collection?: Collection
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Collection>(
    {
      queryKey: [API_ROUTES.COLLECTIONS, id],
      url: `${API_URL}/${API_ROUTES.COLLECTIONS}/${id}/`,
    }
  )

  const collection = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    collection,
    isLoading,
    isFetching,
    error,
  }
}
