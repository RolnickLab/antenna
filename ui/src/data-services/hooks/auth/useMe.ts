import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL, STATUS_CODES } from 'data-services/constants'
import { useUser } from 'utils/user/userContext'

export const useMe = () => {
  const { user, clearToken } = useUser()
  const { data, isLoading, error } = useQuery({
    retry: 1,
    retryDelay: 0,
    queryKey: [API_ROUTES.ME],
    queryFn: async () => {
      if (!user.token) {
        return undefined
      }
      const res = await axios.get<{ id: string; email: string; name?: string }>(
        `${API_URL}/${API_ROUTES.ME}`,
        {
          headers: { Authorization: `Token ${user.token}` },
        }
      )
      return res.data
    },
    onError: (error: any) => {
      if (error.response.status === STATUS_CODES.FORBIDDEN) {
        clearToken()
      }
    },
  })

  return { user: data, isLoading, error }
}
