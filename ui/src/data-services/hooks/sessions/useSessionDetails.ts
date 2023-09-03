import { API_ROUTES } from 'data-services/constants'
import { getFetchDetailsUrl } from 'data-services/utils'
import _ from 'lodash'
import { useMemo } from 'react'
import {
  ServerEventDetails,
  SessionDetails,
} from '../../models/session-details'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

const convertServerRecord = (record: ServerEventDetails) =>
  new SessionDetails(record)

export const useSessionDetails = (
  id: string,
  params: { occurrence?: string; capture?: string }
): {
  session?: SessionDetails
  isLoading: boolean
  isFetching: boolean
  error?: unknown
} => {
  const fetchUrl = getFetchDetailsUrl({
    collection: API_ROUTES.SESSIONS,
    itemId: id,
    queryParams: _.pickBy(params, (param) => param !== undefined),
  })

  const { data, isLoading, isFetching, error } = useAuthorizedQuery<
    ServerEventDetails[]
  >({
    queryKey: [API_ROUTES.SESSIONS, id],
    url: fetchUrl,
  })

  const session = useMemo(
    () => (data ? convertServerRecord(data) : undefined),
    [data]
  )

  return {
    session,
    isLoading,
    isFetching,
    error,
  }
}
