import { TrackEditResult, useTrackAction } from './useTrackAction'

/** Split an occurrence at a detection: that detection and every later one move to a new occurrence. */
export const useSplitTrack = (occurrenceId: string) => {
  const { mutateAsync, ...rest } = useTrackAction<
    { detection_id: number },
    TrackEditResult
  >(occurrenceId, 'split-track')

  return {
    splitTrack: (detectionId: string) =>
      mutateAsync({ detection_id: Number(detectionId) }),
    ...rest,
  }
}
