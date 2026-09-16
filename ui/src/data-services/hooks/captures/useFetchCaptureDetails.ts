import { useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES } from 'data-services/constants'
import {
  CaptureDetails,
  ServerCaptureDetails,
} from 'data-services/models/capture-details'
import { getAuthHeader, getFetchDetailsUrl } from 'data-services/utils'
import { useCallback } from 'react'
import { useUser } from 'utils/user/userContext'

/**
 * Reads one capture on demand, for callers that only learn which capture they need
 * after an edit has landed. Shares its cache entry with `useCaptureDetails`.
 */
export const useFetchCaptureDetails = (projectId: string) => {
  const { user } = useUser()
  const queryClient = useQueryClient()

  return useCallback(
    (id: string) =>
      queryClient
        .fetchQuery({
          queryKey: [API_ROUTES.CAPTURES, id, projectId],
          queryFn: () =>
            axios
              .get<ServerCaptureDetails>(
                getFetchDetailsUrl({
                  collection: API_ROUTES.CAPTURES,
                  itemId: id,
                  projectId,
                }),
                { headers: getAuthHeader(user) }
              )
              .then((res) => res.data),
        })
        .then((record) => new CaptureDetails(record)),
    [projectId, queryClient, user]
  )
}
