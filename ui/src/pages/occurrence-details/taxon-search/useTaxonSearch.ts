import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { useEffect, useState } from 'react'
import { SearchResult, ServerSearchResult } from './types'

const MAX_NUM_RESULTS = 5

const convertServerResult = (result: ServerSearchResult): SearchResult => ({
  id: `${result.id}`,
  name: result.name,
  rank: result.rank,
})

export const useTaxonSearch = (searchString: string) => {
  const [data, setData] = useState<SearchResult[]>()
  const [isLoading, setIsLoading] = useState<boolean>()
  const [error, setError] = useState<Error>()
  const fetchUrl = searchString.length
    ? `${API_URL}/taxa/suggest?q=${searchString}`
    : undefined

  useEffect(() => {
    setError(undefined)
    if (!fetchUrl) {
      setData(undefined)
      setIsLoading(false)
      return
    }
    setIsLoading(true)
    axios
      .get<ServerSearchResult[]>(fetchUrl)
      .then((res) => {
        setData(res.data.map(convertServerResult).slice(0, MAX_NUM_RESULTS))
        setIsLoading(false)
      })
      .catch((error: Error) => {
        setError(error)
        setIsLoading(false)
      })
  }, [fetchUrl])

  return { data, isLoading, error }
}
