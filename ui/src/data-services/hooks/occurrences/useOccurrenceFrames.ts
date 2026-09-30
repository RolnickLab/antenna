import { API_ROUTES, API_URL } from 'data-services/constants'
import {
  convertOccurrenceFrame,
  OccurrenceFrame,
} from 'data-services/models/occurrence-details'
import {
  FramePageRequest,
  getFramePageQuery,
  getLinkedFramePage,
  ServerOccurrenceFramesPage,
} from 'data-services/models/occurrence-frames-page'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuthorizedQuery } from '../auth/useAuthorizedQuery'

/**
 * One page of an occurrence's frames, earliest first. Pages share the occurrence's
 * query key, so every track edit that refreshes the occurrence refreshes them too.
 */
export const useOccurrenceFrames = ({
  enabled = true,
  occurrenceId,
  request,
}: {
  /** Off while the detail's own first page is on screen. */
  enabled?: boolean
  occurrenceId: string
  request: FramePageRequest
}): {
  error?: unknown
  frames?: OccurrenceFrame[]
  isFetching: boolean
  next?: FramePageRequest
  previous?: FramePageRequest
  total?: number
} => {
  // The same bypass as the occurrence itself, or a page of an occurrence opened past
  // the project's default filters would not be found.
  const [searchParams] = useSearchParams()
  const applyDefaults = searchParams.get('apply_defaults')
  const query = getFramePageQuery(request)
  const url = `${API_URL}/${
    API_ROUTES.OCCURRENCES
  }/${occurrenceId}/detections/?${query}${
    applyDefaults === 'false' ? '&apply_defaults=false' : ''
  }`

  const { data, error, isFetching } =
    useAuthorizedQuery<ServerOccurrenceFramesPage>({
      enabled: enabled && !!occurrenceId,
      keepPreviousData: true,
      queryKey: [
        API_ROUTES.OCCURRENCES,
        occurrenceId,
        'detections',
        applyDefaults,
        query,
      ],
      retry: false,
      url,
    })

  const frames = useMemo(
    () => data?.results.map(convertOccurrenceFrame),
    [data]
  )

  return {
    error,
    frames,
    isFetching,
    next: data ? getLinkedFramePage(data.next) : undefined,
    previous: data ? getLinkedFramePage(data.previous) : undefined,
    total: data?.count,
  }
}
