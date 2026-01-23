import { API_ROUTES } from 'data-services/constants'
import { Member, ServerMember } from 'data-services/models/member'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerMember): Member => ({
  addedAt: new Date(record.created_at),
  canDelete: record.user_permissions.includes(UserPermission.Delete),
  canUpdate: record.user_permissions.includes(UserPermission.Update),
  email: record.user.email,
  id: `${record.id}`,
  image: record.user.image,
  name: record.user.name,
  role: {
    description: record.role_description,
    id: record.role,
    name: record.role_display_name,
  },
  updatedAt: record.updated_at ? new Date(record.updated_at) : undefined,
  userId: `${record.user.id}`,
})

export const useMembers = (
  projectId: string,
  params?: FetchParams
): {
  members?: Member[]
  userPermissions?: UserPermission[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerMember[]
    user_permissions?: UserPermission[]
    count: number
  }>({
    queryKey: [API_ROUTES.MEMBERS(projectId), params],
    url: getFetchUrl({
      collection: API_ROUTES.MEMBERS(projectId),
      params,
    }),
  })

  const members = useMemo(() => data?.results.map(convertServerRecord), [data])

  return {
    members,
    userPermissions: data?.user_permissions,
    total: data?.count ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
