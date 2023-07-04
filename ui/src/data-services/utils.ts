import { API_URL } from './constants'
import { FetchParams } from './types'

type QueryParams = { [key: string]: string }

export const getFetchUrl = ({
  collection,
  params,
  queryParams: _queryParams = {},
}: {
  collection: string
  params?: FetchParams
  queryParams?: QueryParams
}) => {
  const queryParams: QueryParams = { ..._queryParams }

  if (params?.sort) {
    const order = params.sort.order === 'asc' ? '' : '-'
    const field = params.sort.field
    queryParams.ordering = `${order}${field}`
  }
  if (params?.pagination) {
    queryParams.limit = `${params?.pagination.perPage}`
    queryParams.offset = `${
      params?.pagination.perPage * params?.pagination.page
    }`
  }
  if (params?.filters?.length) {
    params.filters.forEach((filter) => {
      if (filter.value?.length) {
        queryParams[filter.field] = filter.value
      }
    })
  }

  const baseUrl = `${API_URL}/${collection}`
  const queryString = new URLSearchParams(queryParams).toString()

  if (!queryString.length) {
    return baseUrl
  }

  return `${baseUrl}?${queryString}`
}
