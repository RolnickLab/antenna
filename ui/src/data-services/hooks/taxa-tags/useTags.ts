import { API_ROUTES } from 'data-services/constants'
import { Tag } from 'data-services/models/species'
import { getFetchUrl } from 'data-services/utils'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

export const useTags = (params?: {
  projectId?: string
}): {
  tags?: Tag[]
  userPermissions?: UserPermission[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({
    collection: API_ROUTES.TAGS,
    params,
  })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: Tag[]
    user_permissions?: UserPermission[]
  }>({
    queryKey: [API_ROUTES.TAGS, params],
    url: fetchUrl,
  })

  return {
    tags: data?.results,
    userPermissions: data?.user_permissions,
    isLoading,
    isFetching,
    error,
  }
}
