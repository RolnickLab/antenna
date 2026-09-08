import { FormError } from 'components/form/layout/layout'
import { useMergeOccurrences } from 'data-services/hooks/occurrences/track/useMergeOccurrences'
import { useSetGroupingVerified } from 'data-services/hooks/occurrences/track/useSetGroupingVerified'
import { OccurrenceDetails } from 'data-services/models/occurrence-details'
import { GitMergeIcon, Loader2Icon } from 'lucide-react'
import { Badge, Button } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { OccurrencePicker } from 'components/track/occurrence-picker'
import { TrackEditDialog } from 'components/track/track-edit-dialog'
import { useTrackCandidates } from 'components/track/useTrackCandidates'

export const GroupingActions = ({
  canRestructure,
  canVerify,
  occurrence,
}: {
  canRestructure: boolean
  canVerify: boolean
  occurrence: OccurrenceDetails
}) => {
  const { projectId } = useParams()
  const [mergeOpen, setMergeOpen] = useState(false)
  const [sourceId, setSourceId] = useState<string>()

  const merge = useMergeOccurrences(occurrence.id)
  const {
    setGroupingVerified,
    error: verifyError,
    isLoading: verifyLoading,
  } = useSetGroupingVerified(occurrence.id)

  const frames = occurrence.frames
  const { candidates, isLoading: candidatesLoading } = useTrackCandidates({
    captureIds: mergeOpen
      ? [frames[frames.length - 1]?.captureId, frames[0]?.captureId]
      : [],
    excludeIds: [occurrence.id],
    projectId: projectId as string,
  })

  const verifiedBy = occurrence.groupingVerifiedBy
  const verifiedAt = occurrence.groupingVerifiedAt
  const verifyErrorMessage = verifyError
    ? parseServerError(verifyError).message
    : undefined

  const closeMerge = () => {
    setMergeOpen(false)
    setSourceId(undefined)
    merge.reset()
  }

  return (
    <div className="flex flex-col gap-2 mb-6">
      {occurrence.groupingVerified ? (
        <div className="flex flex-wrap items-center gap-2">
          <Badge label={translate(STRING.TRACK_GROUPING_CONFIRMED)} />
          <span className="body-small text-muted-foreground">
            {translate(STRING.TRACK_GROUPING_CONFIRMED_BY, {
              date: verifiedAt
                ? getFormatedDateTimeString({ date: verifiedAt })
                : translate(STRING.VALUE_NOT_AVAILABLE),
              name: verifiedBy?.name ?? translate(STRING.ANONYMOUS_USER),
            })}
          </span>
        </div>
      ) : (
        <span className="body-small text-muted-foreground">
          {translate(STRING.TRACK_GROUPING_NOT_CONFIRMED)}
        </span>
      )}
      <div className="flex flex-wrap justify-end gap-2">
        {canRestructure && (
          <Button
            onClick={() => setMergeOpen(true)}
            size="small"
            variant="outline"
          >
            <GitMergeIcon className="w-4 h-4" />
            <span>{translate(STRING.TRACK_MERGE)}</span>
          </Button>
        )}
        {canVerify && (
          <Button
            disabled={verifyLoading}
            onClick={() => setGroupingVerified(!occurrence.groupingVerified)}
            size="small"
            variant={occurrence.groupingVerified ? 'outline' : 'default'}
          >
            <span>
              {occurrence.groupingVerified
                ? translate(STRING.TRACK_UNDO_CONFIRMATION)
                : translate(STRING.TRACK_CONFIRM_GROUPING)}
            </span>
            {verifyLoading ? (
              <Loader2Icon className="w-4 h-4 animate-spin" />
            ) : null}
          </Button>
        )}
      </div>
      {verifyErrorMessage ? <FormError message={verifyErrorMessage} /> : null}

      <TrackEditDialog
        confirmDisabled={!sourceId}
        confirmLabel={translate(STRING.TRACK_MERGE)}
        description={translate(STRING.TRACK_MERGE_DESCRIPTION)}
        error={merge.error}
        isLoading={merge.isLoading}
        onConfirm={() => merge.mergeOccurrences([sourceId as string])}
        onOpenChange={(open) => (open ? undefined : closeMerge())}
        open={mergeOpen}
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
    </div>
  )
}
