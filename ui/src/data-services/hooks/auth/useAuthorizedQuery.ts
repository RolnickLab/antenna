import { QueryKey, useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useAuthorizedQuery = <T>({
  enabled,
  onError,
  queryKey = [],
  refetchInterval,
  retry,
  staleTime,
  url,
}: {
  enabled?: boolean
  onError?: (error: unknown) => void
  queryKey?: QueryKey
  refetchInterval?: number
  retry?: number
  staleTime?: number
  url: string
}) => {
  const { user } = useUser()
  const { data, isLoading, isFetching, isSuccess, error } = useQuery({
    enabled,
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

  // React Query v4 has no "idle" status: a disabled query that has never run reports
  // isLoading true forever, since status starts and stays at 'loading'. Callers pass
  // enabled: false to skip a fetch on purpose (e.g. no id to fetch yet), so report
  // isLoading false in that case rather than a spinner that never resolves.
  return {
    data,
    isLoading: enabled === false ? false : isLoading,
    isFetching,
    isSuccess,
    error,
  }
}
