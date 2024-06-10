import { Entity, ServerEntity } from 'data-services/models/entity'
import { Storage } from 'data-services/models/storage'
import { Collection } from 'data-services/models/collection'
import { FetchParams } from 'data-services/types'
import { getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (collection: string, record: ServerEntity) => {
  // TODO: How to handle different types of entities?
  // look at the customFormMap in constants.ts
  if (collection === 'storage') {
    return new Storage(record)
  } else if (collection === 'collection') {
    return new Collection(record)
  }

  return new Entity(record)
}

export const useEntities = (
  collection: string,
  params?: FetchParams
): {
  entities?: Entity[]
  total: number
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection, params })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<{
    results: ServerEntity[]
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
    isLoading,
    isFetching,
    error,
  }
}
