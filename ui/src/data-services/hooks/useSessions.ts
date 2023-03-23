import { ServerEvent, Session } from '../models/session'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerEvent) => new Session(record)

export const useSessions = (): { sessions: Session[]; isLoading: boolean } => {
  const { data, isLoading } = useGetList<ServerEvent, Session>(
    'events',
    convertServerRecord
  )

  return {
    sessions: data,
    isLoading,
  }
}
