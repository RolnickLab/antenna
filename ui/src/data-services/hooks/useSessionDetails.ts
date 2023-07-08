import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { getFetchDetailsUrl } from 'data-services/utils'
import { ServerEventDetails, SessionDetails } from '../models/session-details'

const COLLECTION = 'events'

const convertServerRecord = (record: ServerEventDetails) =>
  new SessionDetails(record)

export const useSessionDetails = (
  id: string,
  occurrenceId?: string
): {
  session?: SessionDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchDetailsUrl({
    collection: COLLECTION,
    itemId: id,
    queryParams: occurrenceId ? { occurrence: occurrenceId } : undefined,
  })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION, id],
    queryFn: () =>
      axios
        .get<ServerEventDetails[]>(fetchUrl)
        .then((res) => convertServerRecord(res.data)),
  })

  return {
    session: data,
    isLoading,
    isFetching,
    error,
  }
}
