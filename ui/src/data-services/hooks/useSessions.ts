import { FetchParams } from 'data-services/types'
import { useMemo } from 'react'
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

  // This extra fetch is only until we have a real API
  const { data: captures, isLoading: capturesAreLoading } = useGetList<
    any,
    any
  >({ collection: 'captures' }, (record: any) => record)
  const sessions = useMemo(
    () =>
      data.map((session) => {
        if (captures.length) {
          session.images = captures
            .filter((capture) => `${capture.event}` === session.id)
            .map((capture) => ({ src: capture.source_image }))
        }
        return session
      }),
    [data, captures]
  )

  return {
    sessions,
    total: 5, // Hard coded until we get this in response
    isLoading: isLoading || capturesAreLoading,
  }
}
