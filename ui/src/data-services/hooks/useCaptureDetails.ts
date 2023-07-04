import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import {
  CaptureDetails,
  ServerCaptureDetails,
} from 'data-services/models/capture-details'

const COLLECTION = 'captures'

const convertServerRecord = (record: ServerCaptureDetails) =>
  new CaptureDetails(record)

export const useCaptureDetails = (
  id: string
): {
  capture?: CaptureDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, id],
    queryFn: () =>
      axios
        .get<CaptureDetails>(`${API_URL}/${COLLECTION}/${id}`)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    capture: data,
    isLoading,
    isFetching,
    error,
  }
}
