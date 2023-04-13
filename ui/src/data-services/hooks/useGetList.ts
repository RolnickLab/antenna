import { API_URL } from 'data-services/constants'
import { FetchParams } from 'data-services/types'
import { useEffect, useState } from 'react'

const fetchData = async <T>(url: string): Promise<T[]> => {
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(
      `${response.status} (${response.statusText ?? 'Server error'})`
    )
  }

  return await response.json()
}

const getUrl = ({
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

export const useGetList = <T1, T2>(
  args: {
    collection: string
    params?: FetchParams
  },
  convertServerRecord: (record: T1) => T2
) => {
  const [data, setData] = useState<T2[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string>()

  const url = getUrl(args)

  useEffect(() => {
    setError(undefined)
    setIsLoading(true)
    fetchData<T1>(url)
      .then((records) => {
        setData(records.map(convertServerRecord))
        setIsLoading(false)
      })
      .catch((error: Error) => {
        setError(error.message)
        setIsLoading(false)
      })
  }, [url])

  return { data, isLoading, error }
}
