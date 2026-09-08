import { useQueries } from '@tanstack/react-query'
import axios from 'axios'
import { API_ROUTES } from 'data-services/constants'
import { Occurrence, ServerOccurrence } from 'data-services/models/occurrence'
import { getAuthHeader, getFetchUrl } from 'data-services/utils'
import { useMemo } from 'react'
import { useUser } from 'utils/user/userContext'

const OCCURRENCES_PER_CAPTURE = 25

/**
 * Occurrences that have a detection in any of the given captures, as one list.
 *
 * One request per capture, so callers pass a handful of captures rather than a
 * session's worth.
 */
export const useOccurrencesInCaptures = ({
  captureIds,
  projectId,
}: {
  captureIds: string[]
  projectId: string
}): {
  occurrences: Occurrence[]
  isLoading: boolean
} => {
  const { user } = useUser()

  // An id that is not a non-empty string would be dropped from the query string,
  // turning one capture's occurrences into every occurrence in the project.
  const requested = captureIds.filter((id) => typeof id === 'string' && !!id)

  const results = useQueries({
    queries: requested.map((captureId) => {
      const params = {
        projectId,
        pagination: { page: 0, perPage: OCCURRENCES_PER_CAPTURE },
        filters: [
          { field: 'detections__source_image', value: captureId },
          // An occurrence a track edit created can score under the project's default
          // threshold, which would keep it out of this list and make that edit
          // impossible to undo from here.
          { field: 'apply_defaults', value: 'false' },
        ],
      }

      return {
        queryKey: [API_ROUTES.OCCURRENCES, params],
        queryFn: () =>
          axios
            .get<{ results: ServerOccurrence[] }>(
              getFetchUrl({ collection: API_ROUTES.OCCURRENCES, params }),
              { headers: getAuthHeader(user) }
            )
            .then((res) => res.data),
      }
    }),
  })

  const occurrences = useMemo(() => {
    const byId = new Map<string, Occurrence>()

    results.forEach((result) => {
      result.data?.results.forEach((record) => {
        const occurrence = new Occurrence(record)
        byId.set(occurrence.id, occurrence)
      })
    })

    return [...byId.values()]
  }, [results.map((result) => result.dataUpdatedAt).join()])

  return {
    occurrences,
    isLoading: results.some((result) => result.isLoading),
  }
}
