import { OccurrencePicker } from 'components/track/occurrence-picker'
import { TrackEditDialog } from 'components/track/track-edit-dialog'
import { useTrackCandidates } from 'components/track/useTrackCandidates'
import { useMergeOccurrences } from 'data-services/hooks/occurrences/track/useMergeOccurrences'
import { useSetGroupingVerified } from 'data-services/hooks/occurrences/track/useSetGroupingVerified'
import { useSplitTrack } from 'data-services/hooks/occurrences/track/useSplitTrack'
import { AlertCircleIcon, Loader2Icon, RouteIcon } from 'lucide-react'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

/**
 * Where the shown path stands, pinned to the capture's corner. The toolbar that
 * requested it closes with its box, so this is what outlives a hover.
 */
export const SessionPathStatus = ({
  error,
  isLoading,
  occurrenceId,
}: {
  error?: boolean
  isLoading?: boolean
  occurrenceId: string
}) => {
  const status = () => {
    if (isLoading) {
      return {
        Icon: Loader2Icon,
        iconClassName: 'animate-spin',
        label: translate(STRING.TRACK_PATH_STATUS_LOADING, {
          id: occurrenceId,
        }),
      }
    }
    if (error) {
      return {
        Icon: AlertCircleIcon,
        iconClassName: 'text-destructive',
        label: translate(STRING.TRACK_PATH_STATUS_ERROR, { id: occurrenceId }),
      }
    }
    return {
      Icon: RouteIcon,
      iconClassName: '',
      label: translate(STRING.TRACK_PATH_STATUS_SHOWN, { id: occurrenceId }),
    }
  }
  const { Icon, iconClassName, label } = status()

  return (
    <span
      className="absolute top-2 left-2 flex items-center gap-2 px-2.5 py-1 rounded-full bg-neutral-900/70 text-generic-white text-xs pointer-events-none select-none"
      role="status"
    >
      <Icon className={`w-3 h-3 ${iconClassName}`} />
      <span>{label}</span>
    </span>
  )
}

export interface SessionTrackEdit {
  action: 'split' | 'merge' | 'verify'
  /** The frame the toolbar was anchored to; the split boundary. */
  detectionId: string
  /** Frames a split would move: this frame and every later one. */
  movedBySplit?: number
  occurrenceId: string
  /** Time of the boundary frame, as the operator saw it when they opened the dialog. */
  timeLabel?: string
  total?: number
  verified?: boolean
}

/**
 * The confirmation dialogs the session toolbar opens.
 *
 * Rendered once for the capture rather than per box: a split moves the clicked frame
 * onto another occurrence, so a dialog owned by that box would be unmounted by the
 * refresh before it could report what happened. For the same reason the split's
 * description arrives already worded, rather than being derived from the live path.
 */
export const SessionTrackEdits = ({
  captureId,
  edit,
  onClose,
}: {
  captureId?: string
  edit?: SessionTrackEdit
  onClose: () => void
}) => {
  const { projectId } = useParams()
  const [sourceId, setSourceId] = useState<string>()

  const occurrenceId = edit?.occurrenceId ?? ''
  const split = useSplitTrack(occurrenceId)
  const merge = useMergeOccurrences(occurrenceId)
  const {
    setGroupingVerified,
    error: verifyError,
    isLoading: verifyLoading,
  } = useSetGroupingVerified(occurrenceId)
  const [verifyDone, setVerifyDone] = useState(false)

  const { candidates, isLoading: candidatesLoading } = useTrackCandidates({
    captureIds: edit?.action === 'merge' ? [captureId, captureId] : [],
    excludeIds: [occurrenceId],
    projectId: projectId as string,
  })

  const close = () => {
    setSourceId(undefined)
    setVerifyDone(false)
    split.reset()
    merge.reset()
    onClose()
  }

  if (!edit) {
    return null
  }

  return (
    <>
      <TrackEditDialog
        confirmLabel={translate(STRING.TRACK_SPLIT_HERE)}
        description={translate(STRING.TRACK_SPLIT_DESCRIPTION, {
          moved: edit.movedBySplit ?? 0,
          time: edit.timeLabel ?? translate(STRING.VALUE_NOT_AVAILABLE),
          total: edit.total ?? 0,
        })}
        error={split.error}
        isLoading={split.isLoading}
        onConfirm={() => split.splitTrack(edit.detectionId)}
        onOpenChange={(open) => (open ? undefined : close())}
        open={edit.action === 'split'}
        result={
          split.result
            ? translate(STRING.TRACK_SPLIT_RESULT, {
                count: split.result.new_occurrence_detections_count,
                id: `${split.result.new_occurrence_id}`,
              })
            : undefined
        }
        resultLink={
          split.result
            ? getAppRoute({
                to: APP_ROUTES.OCCURRENCE_DETAILS({
                  projectId: projectId as string,
                  occurrenceId: `${split.result.new_occurrence_id}`,
                }),
                filters: { apply_defaults: 'false' },
              })
            : undefined
        }
        title={translate(STRING.TRACK_SPLIT_HERE)}
      />

      <TrackEditDialog
        confirmDisabled={!sourceId}
        confirmLabel={translate(STRING.TRACK_MERGE)}
        description={translate(STRING.TRACK_MERGE_DESCRIPTION)}
        error={merge.error}
        isLoading={merge.isLoading}
        onConfirm={() => merge.mergeOccurrences([sourceId as string])}
        onOpenChange={(open) => (open ? undefined : close())}
        open={edit.action === 'merge'}
        result={
          merge.result
            ? translate(STRING.TRACK_MERGE_RESULT, {
                count: merge.result.detections_count,
              })
            : undefined
        }
        title={translate(STRING.TRACK_MERGE)}
      >
        {merge.result ? null : (
          <OccurrencePicker
            candidates={candidates}
            isLoading={candidatesLoading}
            onSelect={setSourceId}
            selectedId={sourceId}
          />
        )}
      </TrackEditDialog>

      <TrackEditDialog
        confirmLabel={
          edit.verified
            ? translate(STRING.TRACK_UNDO_CONFIRMATION)
            : translate(STRING.TRACK_CONFIRM_GROUPING)
        }
        description={
          edit.verified
            ? translate(STRING.TRACK_UNDO_CONFIRMATION_DESCRIPTION)
            : translate(STRING.TRACK_CONFIRM_GROUPING_DESCRIPTION)
        }
        error={verifyError}
        isLoading={verifyLoading}
        onConfirm={() =>
          setGroupingVerified(!edit.verified).then(() => setVerifyDone(true))
        }
        onOpenChange={(open) => (open ? undefined : close())}
        open={edit.action === 'verify'}
        result={
          verifyDone
            ? edit.verified
              ? translate(STRING.TRACK_UNDO_CONFIRMATION_RESULT)
              : translate(STRING.TRACK_CONFIRM_GROUPING_RESULT)
            : undefined
        }
        title={
          edit.verified
            ? translate(STRING.TRACK_UNDO_CONFIRMATION)
            : translate(STRING.TRACK_CONFIRM_GROUPING)
        }
      />
    </>
  )
}
