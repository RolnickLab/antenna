import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { API_URL } from 'data-services/constants'
import { ServerEvent, Session } from '../models/session'

const COLLECTION = 'events'

const convertServerRecord = (record: ServerEvent) => new Session(record)

export const useSessionDetails = (
  id: string
): {
  session?: Session
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, id],
    queryFn: () =>
      axios
        .get<ServerEvent[]>(`${API_URL}/${COLLECTION}/${id}`)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    session: data,
    isLoading,
    isFetching,
    error,
  }
}
