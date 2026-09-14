import { TrackEditDialog } from 'components/track/track-edit-dialog'
import { useAddDetections } from 'data-services/hooks/occurrences/track/useAddDetections'
import { useMergeOccurrences } from 'data-services/hooks/occurrences/track/useMergeOccurrences'
import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { CaptureDetection } from 'data-services/models/capture'
import { Loader2Icon, RouteIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { useExtendOccurrenceId } from '../hooks/useExtendOccurrenceId'

/** A clicked frame whose own occurrence spans several frames, so the reviewer picks what to move. */
export interface ExtendChoice {
  detectionId: string
  frameCount: number
  /** How the clicked occurrence is named in the dialog: its determination and its id. */
  label: string
  occurrenceId: string
}

export interface ExtendTrackState {
  /** The clicked box already belongs to the occurrence being extended. */
  alreadyInTrack: boolean
  cancelChoice: () => void
  choice?: ExtendChoice
  clickBox: (detection: CaptureDetection) => void
  error?: unknown
  /** Frames the occurrence holds after the last edit, before any refetch reports it. */
  frameCount?: number
  isLoading: boolean
  mergeChoice: () => void
  moveChoice: () => void
  occurrenceId?: string
  start: (occurrenceId: string) => void
  stop: () => void
}

/**
 * Extend mode: a box click adds that frame to one occurrence and moves on, instead of
 * selecting the occurrence behind it. It is how a track gets built by hand on a project
 * where no classifier ran. See #1418.
 */
export const useExtendTrack = ({
  captureId,
  onNextCapture,
}: {
  captureId?: string
  onNextCapture?: () => void
}): ExtendTrackState => {
  const { extendOccurrenceId, setExtendOccurrenceId } = useExtendOccurrenceId()
  const [choice, setChoice] = useState<ExtendChoice>()
  const [alreadyInTrack, setAlreadyInTrack] = useState(false)
  const [frameCount, setFrameCount] = useState<number>()
  const add = useAddDetections(extendOccurrenceId ?? '')
  const merge = useMergeOccurrences(extendOccurrenceId ?? '')
  const isLoading = add.isLoading || merge.isLoading

  useEffect(() => {
    // Each capture is its own decision, so a note or a failure from the one before it
    // never carries over into the banner.
    setAlreadyInTrack(false)
    add.reset()
    merge.reset()
  }, [captureId])

  useEffect(() => {
    setChoice(undefined)
    setFrameCount(undefined)
  }, [extendOccurrenceId])

  const finish = (detectionsCount: number) => {
    setChoice(undefined)
    setFrameCount(detectionsCount)
    onNextCapture?.()
  }

  const addFrame = (detectionId: string) =>
    add
      .addDetections([detectionId])
      .then((response) => finish(response.data.detections_count))
      // The rejection is reported through the mutation's error state.
      .catch(() => undefined)

  const clickBox = (detection: CaptureDetection) => {
    if (!extendOccurrenceId || isLoading) {
      return
    }

    setAlreadyInTrack(false)
    add.reset()
    merge.reset()

    if (detection.occurrenceId === extendOccurrenceId) {
      setAlreadyInTrack(true)
      return
    }

    if (detection.occurrenceId && detection.frameCount > 1) {
      setChoice({
        detectionId: detection.id,
        frameCount: detection.frameCount,
        label: `${detection.label} #${detection.occurrenceId}`,
        occurrenceId: detection.occurrenceId,
      })
      return
    }

    addFrame(detection.id)
  }

  return {
    alreadyInTrack,
    cancelChoice: () => setChoice(undefined),
    choice,
    clickBox,
    error: add.error ?? merge.error,
    frameCount,
    isLoading,
    mergeChoice: () => {
      if (choice) {
        merge
          .mergeOccurrences([choice.occurrenceId])
          .then((response) => finish(response.data.detections_count))
          .catch(() => undefined)
      }
    },
    moveChoice: () => {
      if (choice) {
        addFrame(choice.detectionId)
      }
    },
    occurrenceId: extendOccurrenceId,
    start: setExtendOccurrenceId,
    stop: () => setExtendOccurrenceId(undefined),
  }
}

/**
 * What extend mode is doing, pinned to the top of the capture. Unlike the path status
 * it takes the pointer, because leaving the mode and stepping on are done from here.
 */
export const ExtendTrackBanner = ({
  extend,
  occurrenceId,
  onNextCapture,
}: {
  extend: ExtendTrackState
  occurrenceId: string
  onNextCapture?: () => void
}) => {
  const { occurrence } = useOccurrenceDetails(occurrenceId)
  const frameCount = extend.frameCount ?? occurrence?.numDetections
  const errorMessage = extend.error
    ? parseServerError(extend.error).message
    : undefined

  return (
    <div className="absolute top-2 left-2 right-2 flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 rounded-lg border border-border bg-background/95 shadow-md">
      <RouteIcon className="w-4 h-4 text-muted-foreground" />
      <span className="body-small font-medium">
        {translate(STRING.TRACK_EXTEND_STATUS, {
          name: occurrence?.displayName ?? `#${occurrenceId}`,
        })}
      </span>
      {frameCount !== undefined ? (
        <span className="body-small text-muted-foreground">
          {translate(STRING.TRACK_FRAMES_COUNT, { count: frameCount })}
        </span>
      ) : null}
      <span className="body-small text-muted-foreground">
        {translate(STRING.TRACK_EXTEND_HINT)}
      </span>
      {extend.alreadyInTrack ? (
        <span className="body-small text-muted-foreground" role="status">
          {translate(STRING.TRACK_EXTEND_ALREADY_ADDED)}
        </span>
      ) : null}
      {errorMessage ? (
        <span className="body-small text-destructive" role="alert">
          {errorMessage}
        </span>
      ) : null}
      <div className="ml-auto flex items-center gap-1">
        <Button
          disabled={!onNextCapture || extend.isLoading}
          onClick={onNextCapture}
          size="small"
          variant="outline"
        >
          <span>{translate(STRING.TRACK_EXTEND_NEXT_CAPTURE)}</span>
          {extend.isLoading ? (
            <Loader2Icon className="w-4 h-4 animate-spin" />
          ) : null}
        </Button>
        <Button onClick={extend.stop} size="small" variant="ghost">
          <span>{translate(STRING.TRACK_EXTEND_DONE)}</span>
        </Button>
      </div>
    </div>
  )
}

const ExtendCrop = ({
  label,
  src,
  timeLabel,
}: {
  label: string
  src?: string
  timeLabel?: string
}) => (
  <div className="flex flex-col items-center gap-1">
    <div className="w-40 h-40 bg-muted rounded-md overflow-hidden">
      {src ? (
        <img alt="" className="w-full h-full object-contain" src={src} />
      ) : null}
    </div>
    <span className="body-small font-medium">{label}</span>
    <span className="body-small text-muted-foreground tabular-nums">
      {timeLabel ?? translate(STRING.VALUE_NOT_AVAILABLE)}
    </span>
  </div>
)

/**
 * The choice a multi-frame box forces: the whole track joins the one being extended,
 * or only the clicked frame moves across. The two crops are what the decision rests on.
 */
export const ExtendTrackDialog = ({
  choice,
  extend,
  occurrenceId,
}: {
  choice: ExtendChoice
  extend: ExtendTrackState
  occurrenceId: string
}) => {
  const clicked = useOccurrenceDetails(choice.occurrenceId).occurrence
  const extended = useOccurrenceDetails(occurrenceId).occurrence

  const clickedCrop = clicked?.frames.some(
    (frame) => frame.id === choice.detectionId
  )
    ? clicked.getDetectionInfo(choice.detectionId)
    : undefined
  const latestFrameId = extended?.frames[0]?.id
  const latestCrop = latestFrameId
    ? extended?.getDetectionInfo(latestFrameId)
    : undefined

  return (
    <TrackEditDialog
      confirmLabel={translate(STRING.TRACK_EXTEND_MERGE_WHOLE)}
      description={translate(STRING.TRACK_EXTEND_CHOICE_DESCRIPTION, {
        count: choice.frameCount,
        name: choice.label,
      })}
      error={extend.error}
      isLoading={extend.isLoading}
      isWide
      onConfirm={extend.mergeChoice}
      onOpenChange={(open) => (open ? undefined : extend.cancelChoice())}
      open
      title={translate(STRING.TRACK_EXTEND_TITLE)}
    >
      <div className="flex flex-wrap items-start justify-center gap-6">
        <ExtendCrop
          label={translate(STRING.TRACK_EXTEND_CLICKED_FRAME)}
          src={clickedCrop?.image.src}
          timeLabel={clickedCrop?.timeLabel}
        />
        <ExtendCrop
          label={translate(STRING.TRACK_EXTEND_LATEST_FRAME)}
          src={latestCrop?.image.src}
          timeLabel={latestCrop?.timeLabel}
        />
      </div>
      <div className="flex justify-center">
        <Button
          disabled={extend.isLoading}
          onClick={extend.moveChoice}
          size="small"
          variant="outline"
        >
          <span>{translate(STRING.TRACK_EXTEND_MOVE_FRAME)}</span>
        </Button>
      </div>
    </TrackEditDialog>
  )
}
