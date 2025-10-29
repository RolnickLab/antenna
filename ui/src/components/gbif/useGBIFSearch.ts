import axios from 'axios'
import { useEffect, useState } from 'react'
import { GBIFTaxon } from './types'

const BASE_URL = 'https://api.gbif.org/v1/species' // See docs at https://techdocs.gbif.org/en/openapi/v1/species
const DATASET_KEY = 'd7dddbf4-2cf0-4f39-9b2a-bb099caae36c' // GBIF Backbone Taxonomy
const HIGHER_TAXON_KEY = 216 // Insecta
const STATUS = 'ACCEPTED'
const LIMIT = 10

const getFetchUrl = ({
  rank,
  searchString,
}: {
  rank?: string
  searchString: string
}) => {
  if (!searchString.length) {
    return undefined
  }

  let url = `${BASE_URL}/search?datasetKey=${DATASET_KEY}&higherTaxonKey=${HIGHER_TAXON_KEY}&status=${STATUS}&limit=${LIMIT}&q=${searchString}`

  if (rank) {
    url = `${url}&rank=${rank}`
  }

  return url
}

export const useGBIFSearch = (params: {
  rank?: string
  searchString: string
}) => {
  const [data, setData] = useState<GBIFTaxon[]>()
  const [isLoading, setIsLoading] = useState<boolean>()
  const [error, setError] = useState<Error>()
  const fetchUrl = getFetchUrl(params)

  useEffect(() => {
    setError(undefined)

    if (!fetchUrl) {
      setData(undefined)
      setIsLoading(false)
      return
    }

    setIsLoading(true)
    axios
      .get<{ results: GBIFTaxon[] }>(fetchUrl)
      .then((res) => {
        setData(res.data.results)
        setIsLoading(false)
      })
      .catch((error: Error) => {
        setError(error)
        setIsLoading(false)
      })
  }, [fetchUrl])

  return { data, isLoading, error }
}
