import { ServerEvent, Session } from '../models/session'
import { useGetListItem } from './useGetListItem'

const convertServerRecord = (record: ServerEvent) => new Session(record)

export const useSessionDetails = (
  id: string
): { session?: Session; isLoading: boolean; error?: string } => {
  const { data, isLoading, error } = useGetListItem<ServerEvent, Session>(
    { collection: 'events', id },
    convertServerRecord
  )

  return {
    session: data,
    isLoading,
    error,
  }
}
