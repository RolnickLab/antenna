import { CaptureSet } from 'data-services/models/capture-set'
import { Entity, ServerEntity } from 'data-services/models/entity'
import { StorageSource } from 'data-services/models/storage'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { UserPermission } from 'utils/user/types'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (collection: string, record: ServerEntity) => {
  // TODO: How to handle different types of entities?
  // look at the customFormMap in constants.ts
  if (collection === 'storage') {
    return new StorageSource(record)
  } else if (collection === 'capture-set') {
    return new CaptureSet(record)
  }

  return new Entity(record)
}

export const useEntities = (
  collection: string,
  params?: FetchParams
): {
  entities?: Entity[]
  total: number
  userPermissions?: UserPermission[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerEntity[]
    user_permissions?: UserPermission[]
    count: number
  }>({
    queryKey: [collection, params],
    url: fetchUrl,
  })

  const entities = useMemo(
    () =>
      data?.results.map((record) => convertServerRecord(collection, record)),
    [data]
  )

  return {
    entities,
    total: data?.count ?? 0,
    userPermissions: data?.user_permissions,
    isLoading,
    isFetching,
    error,
  }
}
