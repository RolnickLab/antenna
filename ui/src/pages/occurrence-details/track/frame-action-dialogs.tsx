import { useAddDetections } from 'data-services/hooks/occurrences/track/useAddDetections'
import { useRemoveDetection } from 'data-services/hooks/occurrences/track/useRemoveDetection'
import { useSplitTrack } from 'data-services/hooks/occurrences/track/useSplitTrack'
import { OccurrenceDetails } from 'data-services/models/occurrence-details'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { OccurrencePicker } from './occurrence-picker'
import { TrackEditDialog } from './track-edit-dialog'
import { PendingFrameAction } from './types'
import { useTrackCandidates } from './useTrackCandidates'

export const FrameActionDialogs = ({
  occurrence,
  onClose,
  pending,
}: {
  occurrence: OccurrenceDetails
  onClose: () => void
  pending?: PendingFrameAction
}) => {
  const { projectId } = useParams()
  const [targetId, setTargetId] = useState<string>()

  const split = useSplitTrack(occurrence.id)
  const remove = useRemoveDetection(occurrence.id)
  const move = useAddDetections(targetId ?? occurrence.id)
  const { candidates, isLoading: candidatesLoading } = useTrackCandidates({
    captureIds:
      pending?.action === 'move' ? [pending.captureId, pending.captureId] : [],
    excludeIds: [occurrence.id],
    projectId: projectId as string,
  })

  // A split or a removal can leave the new occurrence scoring under the project's
  // default threshold, which hides it from every lookup. Carry the bypass on the link
  // so the operator can still open — and undo — what they just made.
  const openNewOccurrence = (occurrenceId: number) =>
    getAppRoute({
      to: APP_ROUTES.OCCURRENCE_DETAILS({
        projectId: projectId as string,
        occurrenceId: `${occurrenceId}`,
      }),
      filters: { apply_defaults: 'false' },
    })

  const close = () => {
    setTargetId(undefined)
    split.reset()
    remove.reset()
    move.reset()
    onClose()
  }

  if (!pending) {
    return null
  }

  return (
    <>
      <TrackEditDialog
        confirmLabel={translate(STRING.TRACK_SPLIT_HERE)}
        description={translate(STRING.TRACK_SPLIT_DESCRIPTION, {
          moved: pending.movedBySplit,
          time: pending.timeLabel,
          total: pending.total,
        })}
        error={split.error}
        isLoading={split.isLoading}
        onConfirm={() => split.splitTrack(pending.detectionId)}
        onOpenChange={(open) => (open ? undefined : close())}
        open={pending.action === 'split'}
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
            ? openNewOccurrence(split.result.new_occurrence_id)
            : undefined
        }
        title={translate(STRING.TRACK_SPLIT_HERE)}
      />

      <TrackEditDialog
        confirmLabel={translate(STRING.TRACK_REMOVE_FRAME)}
        description={translate(STRING.TRACK_REMOVE_DESCRIPTION, {
          remaining: pending.total - 1,
          time: pending.timeLabel,
          total: pending.total,
        })}
        error={remove.error}
        isLoading={remove.isLoading}
        onConfirm={() => remove.removeDetection(pending.detectionId)}
        onOpenChange={(open) => (open ? undefined : close())}
        open={pending.action === 'remove'}
        result={
          remove.result
            ? translate(STRING.TRACK_REMOVE_RESULT, {
                id: `${remove.result.new_occurrence_id}`,
              })
            : undefined
        }
        resultLink={
          remove.result
            ? openNewOccurrence(remove.result.new_occurrence_id)
            : undefined
        }
        title={translate(STRING.TRACK_REMOVE_FRAME)}
      />

      <TrackEditDialog
        confirmDisabled={!targetId}
        confirmLabel={translate(STRING.TRACK_MOVE_FRAME)}
        description={translate(STRING.TRACK_MOVE_DESCRIPTION, {
          time: pending.timeLabel,
        })}
        error={move.error}
        isLoading={move.isLoading}
        onConfirm={() => move.addDetections([pending.detectionId])}
        onOpenChange={(open) => (open ? undefined : close())}
        open={pending.action === 'move'}
        result={
          move.result
            ? translate(STRING.TRACK_MOVE_RESULT, {
                count: move.result.detections_count,
                id: `${move.result.occurrence_id}`,
              })
            : undefined
        }
        title={translate(STRING.TRACK_MOVE_FRAME)}
      >
        {move.result ? null : (
          <OccurrencePicker
            candidates={candidates}
            isLoading={candidatesLoading}
            onSelect={setTargetId}
            selectedId={targetId}
          />
        )}
      </TrackEditDialog>
    </>
  )
}
