import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { JobDetails, ServerJobDetails } from 'data-services/models/job-details'
import { COLLECTION } from './constants'

const convertServerRecord = (record: ServerJobDetails) => new JobDetails(record)

export const useJobDetails = (
  id: string
): {
  job?: JobDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, id],
    queryFn: () =>
      axios
        .get<ServerJobDetails>(`${API_URL}/${COLLECTION}/${id}`)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    job: data,
    isLoading,
    isFetching,
    error,
  }
}
