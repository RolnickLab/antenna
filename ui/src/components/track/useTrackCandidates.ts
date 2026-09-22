import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import { useOccurrencesInCaptures } from 'data-services/hooks/occurrences/useOccurrencesInCaptures'
import { useMemo } from 'react'

/**
 * Occurrences worth merging with, or moving a frame to: the ones sharing a capture
 * with the edit or with its neighbours. A track that tracking cut short continues
 * in the capture straight after the last frame, and a session holds thousands.
 */
export const useTrackCandidates = ({
  captureIds,
  excludeIds,
  projectId,
}: {
  /** Captures at the edges of the edit: the first and last frame in question. */
  captureIds: (string | undefined)[]
  excludeIds: string[]
  projectId: string
}) => {
  const [firstCaptureId, lastCaptureId] = captureIds

  const first = useCaptureDetails({
    id: firstCaptureId ?? '',
    projectId,
  })
  const last = useCaptureDetails({
    id: lastCaptureId ?? '',
    projectId,
  })

  const neighbourhood = useMemo(
    () =>
      [
        first.capture?.prevCaptureId,
        firstCaptureId,
        lastCaptureId,
        last.capture?.nextCaptureId,
      ].filter((id): id is string => !!id),
    [
      first.capture?.prevCaptureId,
      firstCaptureId,
      lastCaptureId,
      last.capture?.nextCaptureId,
    ]
  )

  const { occurrences, isLoading } = useOccurrencesInCaptures({
    captureIds: neighbourhood,
    projectId,
  })

  const candidates = useMemo(
    () =>
      occurrences
        .filter((occurrence) => !excludeIds.includes(occurrence.id))
        .sort(
          (o1, o2) =>
            new Date(o1.firstAppearanceTimestamp).getTime() -
            new Date(o2.firstAppearanceTimestamp).getTime()
        ),
    [occurrences, excludeIds.join()]
  )

  return {
    candidates,
    // A disabled query still reports itself as loading, so guard on the ids.
    isLoading:
      (!!firstCaptureId && first.isLoading) ||
      (!!lastCaptureId && last.isLoading) ||
      isLoading,
  }
}
