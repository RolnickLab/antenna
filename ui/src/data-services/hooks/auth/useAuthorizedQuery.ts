import { QueryKey, useQuery, UseQueryOptions } from '@tanstack/react-query'
import axios from 'axios'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useAuthorizedQuery = <T>({
  enabled,
  keepPreviousData,
  onError,
  queryKey = [],
  refetchInterval,
  retry,
  staleTime,
  url,
}: {
  enabled?: boolean
  keepPreviousData?: boolean
  onError?: (error: unknown) => void
  queryKey?: QueryKey
  refetchInterval?: number
  retry?: UseQueryOptions<T>['retry']
  staleTime?: number
  url: string
}) => {
  const { user } = useUser()
  const { data, isLoading, isFetching, isSuccess, error, refetch } = useQuery({
    enabled,
    keepPreviousData,
    onError,
    queryKey,
    queryFn: () =>
      axios
        .get<T>(url, {
          headers: getAuthHeader(user),
        })
        .then((res) => res.data),
    refetchInterval,
    retry,
    staleTime,
  })

  return { data, isLoading, isFetching, isSuccess, error, refetch }
}
