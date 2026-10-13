import { API_ROUTES } from 'data-services/constants'
import { Role } from 'data-services/models/role'
import { getFetchUrl } from 'data-services/utils'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

export const useRoles = (
  useInternalCache?: boolean
): {
  roles?: Role[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Role[]>({
    queryKey: [API_ROUTES.ROLES],
    url: getFetchUrl({ collection: API_ROUTES.ROLES }),
    staleTime: useInternalCache ? Infinity : undefined,
  })

  return { roles: data, isLoading, isFetching, error }
}
