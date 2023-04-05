import { ServerEvent, Session } from '../models/session'
import { useGetListItem } from './useGetListItem'

const convertServerRecord = (record: ServerEvent) => new Session(record)

export const useSessionDetails = (
  id: string
): { session?: Session; isLoading: boolean } => {
  const { data, isLoading } = useGetListItem<ServerEvent, Session>(
    { collection: 'events', id },
    convertServerRecord
  )

  return {
    session: data,
    isLoading,
  }
}
