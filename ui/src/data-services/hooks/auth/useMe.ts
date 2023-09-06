import { API_ROUTES, API_URL, STATUS_CODES } from 'data-services/constants'
import { useUser } from 'utils/user/userContext'
import { useAuthorizedQuery } from './useAuthorizedQuery'

export const useMe = () => {
  const { user, clearToken } = useUser()
  const { data, isLoading, error } = useAuthorizedQuery<{
    id: string
    email: string
    name?: string
  }>({
    queryKey: [API_ROUTES.ME],
    url: `${API_URL}/${API_ROUTES.ME}/`,
    onError: (error: any) => {
      if (error.response?.status === STATUS_CODES.FORBIDDEN) {
        if (user.loggedIn) {
          clearToken()
        }
      }
    },
  })

  return { user: data, isLoading, error }
}
