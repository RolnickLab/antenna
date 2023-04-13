import { FetchParams } from 'data-services/types'
import { ServerEvent, Session } from '../models/session'
import { useGetList } from './useGetList'

const convertServerRecord = (record: ServerEvent) => new Session(record)

export const useSessions = (
  params?: FetchParams
): {
  sessions: Session[]
  total: number
  isLoading: boolean
  error?: string
} => {
  const {
    data: sessions,
    isLoading,
    error,
  } = useGetList<ServerEvent, Session>(
    { collection: 'events', params },
    convertServerRecord
  )

  return {
    sessions,
    total: sessions.length, // TODO: Until we get total in response
    isLoading,
    error,
  }
}
