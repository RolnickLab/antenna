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
    queryParams[`${params.sort.field}_order`] = params.sort?.order
  }
  if (params?.pagination) {
    queryParams.limit = `${params?.pagination.perPage}`
    queryParams.offset = `${
      params?.pagination.perPage * params?.pagination.page
    }`
  }

  const baseUrl = `${API_URL}/${collection}`
  const queryString = new URLSearchParams(queryParams).toString()

  if (!queryString.length) {
    return baseUrl
  }

  return `${baseUrl}?${queryString}`
}
