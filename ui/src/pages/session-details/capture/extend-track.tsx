import {
  DisabledReason,
  TrackEditDialog,
} from 'components/track/track-edit-dialog'
import { useAddDetections } from 'data-services/hooks/occurrences/track/useAddDetections'
import { useMergeOccurrences } from 'data-services/hooks/occurrences/track/useMergeOccurrences'
import { useRemoveDetection } from 'data-services/hooks/occurrences/track/useRemoveDetection'
import { useSetGroupingVerified } from 'data-services/hooks/occurrences/track/useSetGroupingVerified'
import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { CaptureDetection } from 'data-services/models/capture'
import { TrackFrame } from 'data-services/models/occurrence-details'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
  InfoIcon,
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
import { ExtendChoice, ExtendPending, getExtendClick } from './extend-click'
import { getTrackNavigation, TrackPosition } from './track-navigation'

/** Why the last box click changed nothing, or why a successful edit did not move on. */
export type ExtendNote = 'no-later-capture' | 'only-frame'

// A track under construction often scores below the project's default threshold.
const EXTEND_FETCH_OPTIONS = { skipDefaultFilters: true }

const NOTES: Record<ExtendNote, { isError?: boolean; string: STRING }> = {
  'no-later-capture': { string: STRING.TRACK_EXTEND_NO_LATER_CAPTURE },
  'only-frame': { isError: true, string: STRING.TRACK_EXTEND_ONLY_FRAME },
}

export interface ExtendTrackState {
  cancelChoice: () => void
  cancelPending: () => void
  choice?: ExtendChoice
  clickBox: (detection: CaptureDetection) => void
  confirmPending: () => void
  error?: unknown
  isLoading: boolean
  mergeChoice: () => void
  moveChoice: () => void
  note?: ExtendNote
  occurrenceId?: string
  /** Where a replaced frame went when moving the clicked frame in then failed. */
  orphanOccurrenceId?: string
  pending?: ExtendPending
  /** Whether the box popovers show; off by default so they never cover the boxes. */
  showDetails: boolean
  start: (occurrenceId: string) => void
  stop: () => void
  toggleDetails: () => void
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
  const { occurrence: track } = useOccurrenceDetails(
    extendOccurrenceId ?? '',
    EXTEND_FETCH_OPTIONS
  )
  const [choice, setChoice] = useState<ExtendChoice>()
  const [note, setNote] = useState<ExtendNote>()
  const [pending, setPending] = useState<ExtendPending>()
  const [orphanOccurrenceId, setOrphanOccurrenceId] = useState<string>()
  const [showDetails, setShowDetails] = useState(false)
  const add = useAddDetections(extendOccurrenceId ?? '')
  const merge = useMergeOccurrences(extendOccurrenceId ?? '')
  const remove = useRemoveDetection(extendOccurrenceId ?? '')
  const isLoading = add.isLoading || merge.isLoading || remove.isLoading
  // An edit can land after the reviewer has stepped to another capture.
  const latest = useRef({ captureId, nextCaptureId })
  latest.current = { captureId, nextCaptureId }

  const clearFeedback = () => {
    setNote(undefined)
    setOrphanOccurrenceId(undefined)
    setPending(undefined)
    add.reset()
    merge.reset()
    remove.reset()
  }

  useEffect(() => {
    // Each capture is its own decision, so a note, a failure or an unconfirmed
    // correction from the one before it never carries over into the banner.
    clearFeedback()
  }, [captureId])

  useEffect(() => {
    setChoice(undefined)
    setNote(undefined)
    setPending(undefined)
    setShowDetails(false)
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
    // Every branch reads the track's frames, so a click waits for them to load.
    if (!extendOccurrenceId || !track || isLoading) {
      return
    }

    clearFeedback()

    const click = getExtendClick({
      captureId,
      detection,
      frames: track.frames,
      occurrenceId: extendOccurrenceId,
    })

    switch (click.kind) {
      case 'add':
        addFrame(click.detectionId)
        break
      case 'choose':
        setChoice(click.choice)
        break
      case 'only-frame':
        setNote('only-frame')
        break
      case 'remove':
      case 'replace':
        setPending(click)
        break
    }
  }

  // Corrections stay on this capture, so the reviewer can click the right box next.
  const confirmPending = () => {
    if (!pending || isLoading) {
      return
    }

    const request =
      pending.kind === 'remove'
        ? remove.removeDetection(pending.detectionId)
        : remove.removeDetection(pending.removeDetectionId).then(({ data }) =>
            add.addDetections([pending.addDetectionId]).catch((error) => {
              setOrphanOccurrenceId(`${data.new_occurrence_id}`)
              throw error
            })
          )

    request
      // The rejection is reported through the mutation's error state.
      .catch(() => undefined)
      .then(() =>
        setPending((current) => (current === pending ? undefined : current))
      )
  }

  return {
    cancelChoice: () => setChoice(undefined),
    cancelPending: () => setPending(undefined),
    choice,
    clickBox,
    confirmPending,
    error: add.error ?? merge.error ?? remove.error,
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
    orphanOccurrenceId,
    pending,
    showDetails,
    start: setExtendOccurrenceId,
    stop: () => setExtendOccurrenceId(undefined),
    toggleDetails: () => setShowDetails((shown) => !shown),
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
  const { occurrence } = useOccurrenceDetails(
    occurrenceId,
    EXTEND_FETCH_OPTIONS
  )
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
  const noteInfo = extend.note ? NOTES[extend.note] : undefined
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
              {total === 1
                ? translate(STRING.TRACK_FRAMES_ONE)
                : translate(STRING.TRACK_FRAMES_COUNT, { count: total })}
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
        {noteInfo ? (
          <span
            className={
              noteInfo.isError
                ? 'body-small text-destructive'
                : 'body-small text-muted-foreground'
            }
            role={noteInfo.isError ? 'alert' : 'status'}
          >
            {translate(noteInfo.string)}
          </span>
        ) : null}
        {errorMessage ? (
          <span className="body-small text-destructive" role="alert">
            {errorMessage}
            {extend.orphanOccurrenceId
              ? ` ${translate(STRING.TRACK_EXTEND_REPLACE_ORPHAN, {
                  id: extend.orphanOccurrenceId,
                })}`
              : null}
          </span>
        ) : null}
      </div>
      {extend.pending ? (
        <div className="flex flex-wrap items-center gap-2">
          <span className="body-small font-medium">
            {extend.pending.kind === 'remove'
              ? translate(STRING.TRACK_EXTEND_REMOVE_PROMPT)
              : translate(STRING.TRACK_EXTEND_REPLACE_PROMPT)}
          </span>
          <Button
            disabled={extend.isLoading}
            onClick={extend.confirmPending}
            size="small"
            variant="destructive"
          >
            <span>
              {extend.pending.kind === 'remove'
                ? translate(STRING.TRACK_EXTEND_REMOVE)
                : translate(STRING.TRACK_EXTEND_REPLACE)}
            </span>
            {extend.isLoading ? (
              <Loader2Icon className="w-4 h-4 animate-spin" />
            ) : null}
          </Button>
          <Button
            disabled={extend.isLoading}
            onClick={extend.cancelPending}
            size="small"
            variant="outline"
          >
            <span>{translate(STRING.CANCEL)}</span>
          </Button>
        </div>
      ) : null}
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
        <BasicTooltip
          asChild
          content={
            extend.showDetails
              ? translate(STRING.TRACK_EXTEND_HIDE_DETAILS)
              : translate(STRING.TRACK_EXTEND_SHOW_DETAILS)
          }
        >
          <Button
            aria-pressed={extend.showDetails}
            onClick={extend.toggleDetails}
            size="small"
            variant={extend.showDetails ? 'secondary' : 'ghost'}
          >
            <InfoIcon className="w-4 h-4" />
            <span>{translate(STRING.TRACK_EXTEND_DETAILS)}</span>
          </Button>
        </BasicTooltip>
        <BasicTooltip asChild content={translate(STRING.TRACK_EXTEND_STOP)}>
          <Button onClick={extend.stop} size="small" variant="ghost">
            <span>{translate(STRING.CLOSE)}</span>
          </Button>
        </BasicTooltip>
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
  const clicked = useOccurrenceDetails(
    choice.occurrenceId,
    EXTEND_FETCH_OPTIONS
  ).occurrence
  const extended = useOccurrenceDetails(
    occurrenceId,
    EXTEND_FETCH_OPTIONS
  ).occurrence

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
