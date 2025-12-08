import { API_ROUTES } from 'data-services/constants'
import { Role } from 'data-services/models/role'
import { getFetchUrl } from 'data-services/utils'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

export const useRoles = (
  projectId: string,
  useInternalCache?: boolean
): {
  roles?: Role[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Role[]>({
    queryKey: [API_ROUTES.ROLES(projectId)],
    url: getFetchUrl({ collection: API_ROUTES.ROLES(projectId) }),
    staleTime: useInternalCache ? Infinity : undefined,
  })

  return { roles: data, isLoading, isFetching, error }
}
