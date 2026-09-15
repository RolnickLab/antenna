import {
  DisabledReason,
  TrackEditDialog,
} from 'components/track/track-edit-dialog'
import { useAddDetections } from 'data-services/hooks/occurrences/track/useAddDetections'
import { useMergeOccurrences } from 'data-services/hooks/occurrences/track/useMergeOccurrences'
import { useSetGroupingVerified } from 'data-services/hooks/occurrences/track/useSetGroupingVerified'
import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { CaptureDetection } from 'data-services/models/capture'
import { TrackFrame } from 'data-services/models/occurrence-details'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
  Loader2Icon,
  RouteIcon,
} from 'lucide-react'
import { BasicTooltip, Button } from 'nova-ui-kit'
import { ReactNode, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { UserPermission } from 'utils/user/types'
import { useExtendOccurrenceId } from '../hooks/useExtendOccurrenceId'
import { getTrackNavigation, TrackPosition } from './track-navigation'

/** A clicked frame whose own occurrence spans several frames, so the reviewer picks what to move. */
export interface ExtendChoice {
  detectionId: string
  frameCount: number
  /** How the clicked occurrence is named in the dialog: its determination and its id. */
  label: string
  occurrenceId: string
}

/** Why the last box click changed nothing, or why a successful edit did not move on. */
export type ExtendNote =
  | 'already-in-track'
  | 'capture-covered'
  | 'no-later-capture'

const NOTE_STRINGS: Record<ExtendNote, STRING> = {
  'already-in-track': STRING.TRACK_EXTEND_ALREADY_ADDED,
  'capture-covered': STRING.TRACK_EXTEND_CAPTURE_COVERED,
  'no-later-capture': STRING.TRACK_EXTEND_NO_LATER_CAPTURE,
}

export interface ExtendTrackState {
  cancelChoice: () => void
  choice?: ExtendChoice
  clickBox: (detection: CaptureDetection) => void
  error?: unknown
  isLoading: boolean
  mergeChoice: () => void
  moveChoice: () => void
  note?: ExtendNote
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
  nextCaptureId,
  onSelectCapture,
}: {
  captureId?: string
  /** Where a successful edit moves on to: the next capture with detections, if any. */
  nextCaptureId?: string
  onSelectCapture: (captureId: string) => void
}): ExtendTrackState => {
  const { extendOccurrenceId, setExtendOccurrenceId } = useExtendOccurrenceId()
  const { occurrence: track } = useOccurrenceDetails(extendOccurrenceId ?? '')
  const [choice, setChoice] = useState<ExtendChoice>()
  const [note, setNote] = useState<ExtendNote>()
  const add = useAddDetections(extendOccurrenceId ?? '')
  const merge = useMergeOccurrences(extendOccurrenceId ?? '')
  const isLoading = add.isLoading || merge.isLoading
  // An edit can land after the reviewer has stepped to another capture.
  const latest = useRef({ captureId, nextCaptureId })
  latest.current = { captureId, nextCaptureId }

  useEffect(() => {
    // Each capture is its own decision, so a note or a failure from the one before it
    // never carries over into the banner.
    setNote(undefined)
    add.reset()
    merge.reset()
  }, [captureId])

  useEffect(() => {
    setChoice(undefined)
    setNote(undefined)
  }, [extendOccurrenceId])

  const finish = (editedCaptureId?: string) => {
    setChoice(undefined)

    if (latest.current.captureId !== editedCaptureId) {
      return
    }

    if (latest.current.nextCaptureId) {
      onSelectCapture(latest.current.nextCaptureId)
    } else {
      setNote('no-later-capture')
    }
  }

  const addFrame = (detectionId: string) =>
    add
      .addDetections([detectionId])
      .then(() => finish(captureId))
      // The rejection is reported through the mutation's error state.
      .catch(() => undefined)

  const clickBox = (detection: CaptureDetection) => {
    if (!extendOccurrenceId || isLoading) {
      return
    }

    setNote(undefined)
    add.reset()
    merge.reset()

    if (detection.occurrenceId === extendOccurrenceId) {
      setNote('already-in-track')
      return
    }

    // One animal cannot appear twice in the same capture.
    if (track?.frames.some((frame) => frame.captureId === captureId)) {
      setNote('capture-covered')
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
    cancelChoice: () => setChoice(undefined),
    choice,
    clickBox,
    error: add.error ?? merge.error,
    isLoading,
    mergeChoice: () => {
      if (choice) {
        merge
          .mergeOccurrences([choice.occurrenceId])
          .then(() => finish(captureId))
          .catch(() => undefined)
      }
    },
    moveChoice: () => {
      if (choice) {
        addFrame(choice.detectionId)
      }
    },
    note,
    occurrenceId: extendOccurrenceId,
    start: setExtendOccurrenceId,
    stop: () => setExtendOccurrenceId(undefined),
  }
}

const describePosition = (position: TrackPosition, total: number) => {
  switch (position.kind) {
    case 'frame':
      return translate(STRING.TRACK_POSITION_FRAME, {
        index: position.index,
        total,
      })
    case 'between':
      return translate(STRING.TRACK_POSITION_BETWEEN, {
        after: position.before + 1,
        before: position.before,
      })
    case 'before-first':
      return translate(STRING.TRACK_POSITION_BEFORE_FIRST)
    case 'after-last':
      return translate(STRING.TRACK_POSITION_AFTER_LAST)
  }
}

const TrackNavButton = ({
  children,
  label,
  onSelectCapture,
  targetCaptureId,
}: {
  children: ReactNode
  label: string
  onSelectCapture: (captureId: string) => void
  targetCaptureId?: string
}) => (
  <BasicTooltip asChild content={label}>
    <Button
      aria-label={label}
      disabled={!targetCaptureId}
      onClick={() => {
        if (targetCaptureId) {
          onSelectCapture(targetCaptureId)
        }
      }}
      size="icon"
      variant="outline"
    >
      {children}
    </Button>
  </BasicTooltip>
)

/**
 * What extend mode is doing, above the capture so it never covers a box. The track
 * buttons step between the track's own frames rather than every capture.
 */
export const ExtendTrackBanner = ({
  captureDate,
  captureId,
  extend,
  occurrenceId,
  onSelectCapture,
}: {
  captureDate?: Date
  captureId?: string
  extend: ExtendTrackState
  occurrenceId: string
  onSelectCapture: (captureId: string) => void
}) => {
  const { projectId } = useParams()
  const { occurrence } = useOccurrenceDetails(occurrenceId)
  const verify = useSetGroupingVerified(occurrenceId)
  const navigation = getTrackNavigation({
    captureDate,
    captureId,
    frames: occurrence?.frames ?? [],
  })
  const { first, last, position, total } = navigation
  const canVerify =
    !!occurrence?.userPermissions.includes(UserPermission.Update) ||
    !!occurrence?.userPermissions.includes(UserPermission.Delete)
  const error = extend.error ?? verify.error
  const errorMessage = error ? parseServerError(error).message : undefined
  const occurrenceRoute = getAppRoute({
    to: APP_ROUTES.OCCURRENCE_DETAILS({
      projectId: projectId as string,
      occurrenceId,
    }),
    filters: { apply_defaults: 'false' },
  })

  const targetOf = (frame?: TrackFrame) =>
    total > 1 && frame?.captureId !== captureId ? frame?.captureId : undefined

  let timeSpan: string | undefined
  if (first && last) {
    timeSpan =
      first === last
        ? first.timeLabel
        : translate(STRING.TRACK_TIME_SPAN, {
            end: last.timeLabel,
            start: first.timeLabel,
          })
  }

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-2 py-2 border-b border-border md:px-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 min-w-0">
        <RouteIcon className="w-4 h-4 text-muted-foreground" />
        <span className="body-small text-muted-foreground">
          {translate(STRING.TRACK_EXTEND_LABEL)}
        </span>
        <Link
          className="body-small font-medium text-primary"
          to={occurrenceRoute}
        >
          {occurrence?.displayName ?? `#${occurrenceId}`}
        </Link>
        {occurrence ? (
          <>
            <span className="body-small text-muted-foreground">
              {translate(STRING.TRACK_FRAMES_COUNT, { count: total })}
            </span>
            {timeSpan ? (
              <span className="body-small text-muted-foreground tabular-nums">
                {timeSpan}
              </span>
            ) : null}
            {position ? (
              <span className="body-small text-muted-foreground">
                {describePosition(position, total)}
              </span>
            ) : null}
            <span className="body-small text-muted-foreground">
              {occurrence.groupingVerified
                ? translate(STRING.TRACK_GROUPING_CONFIRMED)
                : translate(STRING.TRACK_GROUPING_UNCONFIRMED)}
            </span>
          </>
        ) : null}
        {extend.isLoading ? (
          <Loader2Icon className="w-4 h-4 animate-spin text-muted-foreground" />
        ) : null}
        {extend.note ? (
          <span className="body-small text-muted-foreground" role="status">
            {translate(NOTE_STRINGS[extend.note])}
          </span>
        ) : null}
        {errorMessage ? (
          <span className="body-small text-destructive" role="alert">
            {errorMessage}
          </span>
        ) : null}
      </div>
      <div className="ml-auto flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1">
          <TrackNavButton
            label={translate(STRING.TRACK_FIRST_FRAME)}
            onSelectCapture={onSelectCapture}
            targetCaptureId={targetOf(first)}
          >
            <ChevronsLeftIcon className="w-4 h-4" />
          </TrackNavButton>
          <TrackNavButton
            label={translate(STRING.TRACK_PREVIOUS_FRAME)}
            onSelectCapture={onSelectCapture}
            targetCaptureId={targetOf(navigation.previous)}
          >
            <ChevronLeftIcon className="w-4 h-4" />
          </TrackNavButton>
          <TrackNavButton
            label={translate(STRING.TRACK_NEXT_FRAME)}
            onSelectCapture={onSelectCapture}
            targetCaptureId={targetOf(navigation.next)}
          >
            <ChevronRightIcon className="w-4 h-4" />
          </TrackNavButton>
          <TrackNavButton
            label={translate(STRING.TRACK_LAST_FRAME)}
            onSelectCapture={onSelectCapture}
            targetCaptureId={targetOf(last)}
          >
            <ChevronsRightIcon className="w-4 h-4" />
          </TrackNavButton>
        </div>
        {occurrence && canVerify ? (
          <Button
            disabled={verify.isLoading}
            onClick={() =>
              verify
                .setGroupingVerified(!occurrence.groupingVerified)
                // The rejection is reported through the mutation's error state.
                .catch(() => undefined)
            }
            size="small"
            variant={occurrence.groupingVerified ? 'outline' : 'default'}
          >
            <span>
              {occurrence.groupingVerified
                ? translate(STRING.TRACK_UNDO_CONFIRMATION)
                : translate(STRING.TRACK_CONFIRM_GROUPING)}
            </span>
            {verify.isLoading ? (
              <Loader2Icon className="w-4 h-4 animate-spin" />
            ) : null}
          </Button>
        ) : null}
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

  // One animal cannot appear twice in a capture, so nothing may land on a capture
  // the extended track already covers.
  const coveredCaptureIds = new Set(
    extended?.frames.map((frame) => frame.captureId)
  )
  const isCovered = (captureId?: string) =>
    !!captureId && coveredCaptureIds.has(captureId)
  const clickedFrame = clicked?.frames.find(
    (frame) => frame.id === choice.detectionId
  )
  const mergeBlocked = !!clicked?.frames.some((frame) =>
    isCovered(frame.captureId)
  )
  const moveBlocked = isCovered(clickedFrame?.captureId)

  const clickedCrop = clickedFrame
    ? clicked?.getDetectionInfo(choice.detectionId)
    : undefined
  const latestFrameId = extended?.frames[0]?.id
  const latestCrop = latestFrameId
    ? extended?.getDetectionInfo(latestFrameId)
    : undefined

  return (
    <TrackEditDialog
      confirmDisabled={!clicked || !extended || mergeBlocked}
      confirmDisabledReason={
        mergeBlocked ? translate(STRING.TRACK_EXTEND_MERGE_OVERLAPS) : undefined
      }
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
        <DisabledReason
          reason={
            moveBlocked
              ? translate(STRING.TRACK_EXTEND_CAPTURE_COVERED)
              : undefined
          }
        >
          <Button
            disabled={extend.isLoading || moveBlocked}
            onClick={extend.moveChoice}
            size="small"
            variant="outline"
          >
            <span>{translate(STRING.TRACK_EXTEND_MOVE_FRAME)}</span>
          </Button>
        </DisabledReason>
      </div>
    </TrackEditDialog>
  )
}
