import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { COLLECTION } from './constants'
import { PageDetails } from './types'

export const usePageDetails = (
  slug: string
): {
  page?: PageDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, slug],
    queryFn: () =>
      axios
        .get<PageDetails>(`${API_URL}/${COLLECTION}/${slug}`)
        .then((res) => res.data),
  })

  return {
    page: data,
    isLoading,
    isFetching,
    error,
  }
}
