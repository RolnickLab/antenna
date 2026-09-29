import { OccurrenceGroupingResult, useTrackAction } from './useTrackAction'

/** Move detections into this occurrence from wherever they are now. */
export const useAddDetections = (occurrenceId: string) => {
  const { mutateAsync, ...rest } = useTrackAction<
    { detection_ids: number[] },
    OccurrenceGroupingResult
  >(occurrenceId, 'add-detections')

  return {
    addDetections: (detectionIds: string[]) =>
      mutateAsync({ detection_ids: detectionIds.map(Number) }),
    ...rest,
  }
}
