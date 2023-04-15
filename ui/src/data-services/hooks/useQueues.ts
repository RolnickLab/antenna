import { Queue, ServerQueue } from '../models/queue'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerQueue) => new Queue(record)

export const useQueues = (): {
  queues: Queue[]
  isLoading: boolean
  error?: string
} => {
  const { data, isLoading, error } = useGetList<ServerQueue, Queue>(
    { collection: 'status/queues' },
    convertServerRecord
  )

  return { queues: data, isLoading, error }
}
