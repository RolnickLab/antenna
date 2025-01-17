import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { ServerTaxon, Taxon } from 'data-services/models/taxa'
import _ from 'lodash'
import { useEffect, useState } from 'react'

const MAX_NUM_RESULTS = 5

const convertServerResults = (result: ServerTaxon[]): Taxon[] => {
  const taxa: Taxon[] = []

  result.forEach((serverTaxon) => {
    taxa.push(new Taxon(serverTaxon))

    let serverParent: ServerTaxon | undefined = serverTaxon.parent
    while (serverParent) {
      taxa.push(new Taxon(serverParent))
      serverParent = serverParent.parent
    }
  })

  return _.unionWith(taxa, (t1, t2) => t1.id === t2.id)
}

export const useTaxonSearch = (searchString: string) => {
  const [data, setData] = useState<Taxon[]>()
  const [isLoading, setIsLoading] = useState<boolean>()
  const [error, setError] = useState<Error>()
  const fetchUrl = searchString.length
    ? `${API_URL}/taxa/suggest?q=${searchString}&limit=${MAX_NUM_RESULTS}`
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
        setData(convertServerResults(res.data))
        setIsLoading(false)
      })
      .catch((error: Error) => {
        setError(error)
        setIsLoading(false)
      })
  }, [fetchUrl])

  return { data, isLoading, error }
}
