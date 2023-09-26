import { API_ROUTES, API_URL, STATUS_CODES } from 'data-services/constants'
import { useMemo } from 'react'
import { useUser } from 'utils/user/userContext'
import { useAuthorizedQuery } from './useAuthorizedQuery'

type ServerUserInfo = any // TODO: Update this type

const REFETCH_INTERVAL = 10000 // Refetch every 10 second

export const useUserInfo = () => {
  const { user, clearToken } = useUser()
  const { data, isLoading, error } = useAuthorizedQuery<ServerUserInfo>({
    queryKey: [API_ROUTES.ME],
    url: `${API_URL}/${API_ROUTES.ME}/`,
    refetchInterval: REFETCH_INTERVAL,
    retry: 0,
    onError: (error: any) => {
      if (error.response?.status === STATUS_CODES.FORBIDDEN) {
        if (user.loggedIn) {
          clearToken()
        }
      }
    },
  })

  const userInfo = useMemo(() => {
    if (!data) {
      return
    }

    return {
      ...data,
      id: `${data?.id}`,
    }
  }, [data])

  return { userInfo, isLoading, error }
}
