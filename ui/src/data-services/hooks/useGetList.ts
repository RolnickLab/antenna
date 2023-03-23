import { API_URL } from 'data-services/constants'
import { useEffect, useState } from 'react'

const fetchList = async <T>(collection: string): Promise<T[]> => {
  const response = await fetch(`${API_URL}/${collection}`)

  return await response.json()
}

export const useGetList = <T1, T2>(
  collection: string,
  convertServerRecord: (record: T1) => T2
) => {
  const [data, setData] = useState<T2[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchList<T1>(collection).then((records) => {
      setData(records.map(convertServerRecord))
      setIsLoading(false)
    })
  }, [])

  return { data, isLoading }
}
