import { API_URL } from 'data-services/constants'
import { useEffect, useState } from 'react'

const fetchData = async <T>(url: string): Promise<T> => {
  const response = await fetch(url)

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

  const url = `${API_URL}/${args.collection}/${args.id}`

  useEffect(() => {
    setIsLoading(true)
    fetchData<T1>(url).then((record) => {
      setData(convertServerRecord(record))
      setIsLoading(false)
    })
  }, [url])

  return { data, isLoading }
}
