import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { getFetchUrl } from 'data-services/utils'
import { COLLECTION } from './constants'
import { Page } from './types'

export const usePages = (): {
  pages?: Page[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: COLLECTION })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION],
    queryFn: () =>
      axios.get<{ results: Page[] }>(fetchUrl).then((res) => res.data.results),
  })

  return {
    pages: data,
    isLoading,
    isFetching,
    error,
  }
}
