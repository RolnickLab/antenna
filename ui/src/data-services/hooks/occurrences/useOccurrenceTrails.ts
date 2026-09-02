import { useQueries } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  OccurrenceDetails,
  ServerOccurrenceDetails,
  TrackFrame,
} from 'data-services/models/occurrence-details'
import { getAuthHeader } from 'data-services/utils'
import { useMemo } from 'react'
import { useUser } from 'utils/user/userContext'

export interface OccurrenceTrail {
  /** Every frame of the occurrence, earliest first. */
  frames: TrackFrame[]
  occurrenceId: string
}

/**
 * Where each of these occurrences was in every frame it appears in, so a capture
 * can be drawn with the rest of the animal's path over it.
 */
export const useOccurrenceTrails = (
  occurrenceIds: string[]
): { trails: OccurrenceTrail[] } => {
  const { user } = useUser()

  const results = useQueries({
    queries: occurrenceIds.map((occurrenceId) => ({
      queryKey: [API_ROUTES.OCCURRENCES, occurrenceId],
      queryFn: () =>
        axios
          .get<ServerOccurrenceDetails>(
            `${API_URL}/${API_ROUTES.OCCURRENCES}/${occurrenceId}/`,
            { headers: getAuthHeader(user) }
          )
          .then((res) => res.data),
    })),
  })

  const trails = useMemo(
    () =>
      results.reduce((collected: OccurrenceTrail[], result) => {
        if (result.data) {
          const occurrence = new OccurrenceDetails(result.data)
          collected.push({
            frames: [...occurrence.frames].reverse(),
            occurrenceId: occurrence.id,
          })
        }

        return collected
      }, []),
    [results.map((result) => result.dataUpdatedAt).join()]
  )

  return { trails }
}
