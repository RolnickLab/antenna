import { OccurrenceGroupingResult, useTrackAction } from './useTrackAction'

/**
 * Record or withdraw a person's confirmation that an occurrence holds the right detections.
 *
 * Two endpoints behind one control, because callers only ever offer the operator a
 * toggle. Callers get the state of whichever direction they last ran.
 */
export const useSetGroupingVerified = (occurrenceId: string) => {
  const verify = useTrackAction<undefined, OccurrenceGroupingResult>(
    occurrenceId,
    'verify-grouping'
  )
  const unverify = useTrackAction<undefined, OccurrenceGroupingResult>(
    occurrenceId,
    'unverify-grouping'
  )

  return {
    setGroupingVerified: (verified: boolean) =>
      verified
        ? verify.mutateAsync(undefined)
        : unverify.mutateAsync(undefined),
    error: verify.error ?? unverify.error,
    isLoading: verify.isLoading || unverify.isLoading,
  }
}
