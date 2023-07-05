import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { ServerEventDetails, SessionDetails } from '../models/session-details'

const COLLECTION = 'events'

const convertServerRecord = (record: ServerEventDetails) =>
  new SessionDetails(record)

export const useSessionDetails = (
  id: string
): {
  session?: SessionDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, id],
    queryFn: () =>
      axios
        .get<ServerEventDetails[]>(`${API_URL}/${COLLECTION}/${id}`)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    session: data,
    isLoading,
    isFetching,
    error,
  }
}
