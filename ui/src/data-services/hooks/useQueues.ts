import { Queue, ServerQueue } from '../models/queue'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerQueue) => new Queue(record)

export const useQueues = (): { queues: Queue[]; isLoading: boolean } => {
  const { data, isLoading } = useGetList<ServerQueue, Queue>(
    { collection: 'queues' },
    convertServerRecord
  )

  return { queues: data, isLoading }
}
