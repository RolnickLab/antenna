import { FetchSettings } from 'data-services/types'
import { ServerEvent, Session } from '../models/session'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerEvent) => new Session(record)

export const useSessions = (
  settings?: FetchSettings
): { sessions: Session[]; isLoading: boolean } => {
  const { data, isLoading } = useGetList<ServerEvent, Session>(
    { collection: 'events', settings },
    convertServerRecord
  )

  return {
    sessions: data,
    isLoading,
  }
}
