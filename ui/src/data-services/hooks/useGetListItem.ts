import { API_URL } from 'data-services/constants'
import { useEffect, useState } from 'react'

const fetchData = async <T>(url: string): Promise<T> => {
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(
      `${response.status} (${response.statusText ?? 'Server error'})`
    )
  }

  return await response.json()
}

export const useGetListItem = <T1, T2>(
  args: {
    collection: string
    id: string
  },
  convertServerRecord: (record: T1) => T2
) => {
  const [data, setData] = useState<T2>()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string>()

  const url = `${API_URL}/${args.collection}/${args.id}`

  useEffect(() => {
    setError(undefined)
    setIsLoading(true)
    fetchData<T1>(url)
      .then((record) => {
        setData(convertServerRecord(record))
        setIsLoading(false)
      })
      .catch((error: Error) => {
        setError(error.message)
        setIsLoading(false)
      })
  }, [url])

  return { data, isLoading, error }
}
