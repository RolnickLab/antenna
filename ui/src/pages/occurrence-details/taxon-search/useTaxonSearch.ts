import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { ServerTaxon, Taxon } from 'data-services/models/taxa'
import { useEffect, useState } from 'react'

const MAX_NUM_RESULTS = 5

const convertServerResult = (result: ServerTaxon): Taxon => new Taxon(result)

export const useTaxonSearch = (searchString: string) => {
  const [data, setData] = useState<Taxon[]>()
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
      .get<ServerTaxon[]>(fetchUrl)
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
