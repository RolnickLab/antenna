import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import { getFetchUrl } from 'data-services/utils'
import { ServerOccurrence } from '../models/occurrence'
import { Queue, ServerQueue } from '../models/queue'

const COLLECTION = 'status/queues'

const convertServerRecord = (record: ServerQueue) => new Queue(record)

export const useQueues = (): {
  queues?: Queue[]
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchUrl({ collection: COLLECTION })

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: [COLLECTION],
    queryFn: () =>
      axios
        .get<ServerOccurrence[]>(fetchUrl)
        .then((res) => res.data.map(convertServerRecord)),
  })

  return { queues: data, isLoading, isFetching, error }
}
