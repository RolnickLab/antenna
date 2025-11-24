import { API_ROUTES } from 'data-services/constants'
import { Role } from 'data-services/models/role'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

export const useRoles = (
  params?: FetchParams
): {
  roles?: Role[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<Role[]>({
    queryKey: [API_ROUTES.ROLES, params],
    url: getFetchUrl({
      collection: API_ROUTES.ROLES,
      params,
    }),
  })

  return { roles: data, isLoading, isFetching, error }
}
