import { User } from 'utils/user/types'
import { API_URL } from './constants'
import { FetchParams } from './types'

type QueryParams = { [key: string]: string }

export const getFetchUrl = ({
  collection,
  params,
}: {
  collection: string
  params?: FetchParams
}) => {
  const queryParams: QueryParams = {}

  if (params?.projectId) {
    queryParams.project = params?.projectId
  }
  if (params?.sort) {
    const order = params.sort.order === 'asc' ? '' : '-'
    const field = params.sort.field
    queryParams.ordering = `${order}${field}`
  }
  if (params?.pagination) {
    queryParams.limit = `${params.pagination.perPage}`
    queryParams.offset = `${params.pagination.perPage * params.pagination.page}`
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

export const getFetchDetailsUrl = ({
  collection,
  itemId,
  queryParams = {},
}: {
  collection: string
  itemId: string
  queryParams?: QueryParams
}) => {
  const baseUrl = `${API_URL}/${collection}/${itemId}`
  const queryString = new URLSearchParams(queryParams).toString()

  if (!queryString.length) {
    return baseUrl
  }

  return `${baseUrl}?${queryString}`
}

export const serverErrorToString = (error: any): string => {
  if (error.response?.data) {
    const [field, details] = Object.entries(error.response.data)[0]
    if (field) {
      if (field === 'non_field_errors') {
        return `${details}`
      }
      return `Please check field "${field}". ${details}`
    }
  } else if (error.message) {
    return error.message
  }

  return 'Unknown error'
}

export const getAuthHeader = (user: User) => {
  return user.token ? { Authorization: `Token ${user.token}` } : undefined
}
