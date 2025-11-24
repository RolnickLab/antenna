import { API_ROUTES } from 'data-services/constants'
import { Member } from 'data-services/models/member'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: any): Member => ({
  email: record.user.email,
  id: `${record.user.id}`,
  image: record.user.image,
  name: record.user.name,
  role: {
    displayName: record.role, // TODO: Can we get the display name from backend?
    id: record.role,
  },
})

export const useMembers = (
  params?: FetchParams
): {
  members?: Member[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({
    collection: API_ROUTES.MEMBERS,
    params,
  })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<any[]>({
    queryKey: [API_ROUTES.MEMBERS, params],
    url: fetchUrl,
  })

  const members = useMemo(() => data?.map(convertServerRecord), [data])

  return {
    members,
    total: data?.length ?? 0,
    isLoading,
    isFetching,
    error,
  }
}
