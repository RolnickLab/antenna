import axios from 'axios'
import { MarkerPosition } from 'design-system/map/types'
import _ from 'lodash'
import { useEffect, useState } from 'react'
import { SearchResult, ServerSearchResult } from './types'

const API_URL = '/nominatim'
const MAX_NUM_RESULTS = 5

const convertServerResult = (result: ServerSearchResult): SearchResult => {
  const latitude = _.toNumber(result.lat)
  const longitude = _.toNumber(result.lon)

  return {
    osmId: result.osm_id,
    displayName: result.display_name,
    position: new MarkerPosition(latitude, longitude),
  }
}

const getFetchUrl = (searchString: string) => {
  if (searchString.length) {
    return `${API_URL}?format=json&q=${searchString}`
  }
}

export const useGeoSearch = (searchString: string) => {
  const [data, setData] = useState<SearchResult[]>()
  const [isLoading, setIsLoading] = useState<boolean>()
  const [error, setError] = useState<Error>()
  const fetchUrl = getFetchUrl(searchString)

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
