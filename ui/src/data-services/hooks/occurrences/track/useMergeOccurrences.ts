import { OccurrenceGroupingResult, useTrackAction } from './useTrackAction'

/** Absorb other occurrences into this one. They are deleted; their detections and identifications move here. */
export const useMergeOccurrences = (occurrenceId: string) => {
  const { mutateAsync, ...rest } = useTrackAction<
    { occurrence_ids: number[] },
    OccurrenceGroupingResult
  >(occurrenceId, 'merge')

  return {
    mergeOccurrences: (occurrenceIds: string[]) =>
      mutateAsync({ occurrence_ids: occurrenceIds.map(Number) }),
    ...rest,
  }
}
