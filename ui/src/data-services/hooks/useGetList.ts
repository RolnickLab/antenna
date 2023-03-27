import { API_URL } from 'data-services/constants'
import { FetchSettings } from 'data-services/types'
import { useEffect, useState } from 'react'

const fetchData = async <T>(url: string): Promise<T[]> => {
  const response = await fetch(url)

  return await response.json()
}

const createFetchListUrl = ({
  collection,
  settings,
}: {
  collection: string
  settings?: FetchSettings
}) => {
  const queryParams: { [key: string]: string } = {}
  if (settings?.sort) {
    queryParams[`${settings.sort.field}_order`] = settings.sort?.order
  }
  if (settings?.pagination) {
    queryParams.limit = `${settings?.pagination.perPage}`
    queryParams.offset = `${
      settings?.pagination.perPage * settings?.pagination.page
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
    settings?: FetchSettings
  },
  convertServerRecord: (record: T1) => T2
) => {
  const [data, setData] = useState<T2[]>([])
  const [isLoading, setIsLoading] = useState(true)

  const url = createFetchListUrl(args)

  useEffect(() => {
    setIsLoading(true)
    fetchData<T1>(url).then((records) => {
      setData(records.map(convertServerRecord))
      setIsLoading(false)
    })
  }, [url])

  return { data, isLoading }
}
