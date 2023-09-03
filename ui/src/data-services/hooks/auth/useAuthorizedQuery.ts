import { QueryKey, useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { STATUS_CODES } from 'data-services/constants'
import { getAuthHeader } from 'data-services/utils'
import { useUser } from 'utils/user/userContext'

export const useAuthorizedQuery = <T>({
  refetchInterval,
  queryKey,
  url,
}: {
  refetchInterval?: number
  queryKey: QueryKey
  url: string
}) => {
  const { user, clearToken } = useUser()

  const { data, isLoading, isFetching, error } = useQuery({
    refetchInterval,
    retry: 1,
    retryDelay: 0,
    queryKey,
    queryFn: async () => {
      const res = await axios.get<T>(url, {
        headers: getAuthHeader(user),
      })
      return res.data
    },
    onError: (error: any) => {
      if (error.response?.status === STATUS_CODES.FORBIDDEN) {
        clearToken()
        // TODO: Invalidate queries here
      }
    },
  })

  return { data, isLoading, isFetching, error }
}
