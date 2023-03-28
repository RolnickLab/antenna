import { FetchParams } from 'data-services/types'
import { ServerEvent, Session } from '../models/session'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerEvent) => new Session(record)

export const useSessions = (
  params?: FetchParams
): { sessions: Session[]; total: number; isLoading: boolean } => {
  const { data, isLoading } = useGetList<ServerEvent, Session>(
    { collection: 'events', params },
    convertServerRecord
  )

  return {
    sessions: data,
    total: 5, // Hard coded until we get this in response
    isLoading,
  }
}
