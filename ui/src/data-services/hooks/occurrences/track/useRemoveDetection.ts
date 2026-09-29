import { TrackEditResult, useTrackAction } from './useTrackAction'

/** Pull one detection out of an occurrence into an occurrence of its own. */
export const useRemoveDetection = (occurrenceId: string) => {
  const { mutateAsync, ...rest } = useTrackAction<
    { detection_id: number },
    TrackEditResult
  >(occurrenceId, 'remove-detection')

  return {
    removeDetection: (detectionId: string) =>
      mutateAsync({ detection_id: Number(detectionId) }),
    ...rest,
  }
}
