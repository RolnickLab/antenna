import { API_URL } from './constants'
import { FetchParams } from './types'

export const getFetchUrl = ({
  collection,
  params,
}: {
  collection: string
  params?: FetchParams
}) => {
  const queryParams: { [key: string]: string } = {}
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
