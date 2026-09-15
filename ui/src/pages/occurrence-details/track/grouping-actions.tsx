import { FormError } from 'components/form/layout/layout'
import { useMergeOccurrences } from 'data-services/hooks/occurrences/track/useMergeOccurrences'
import { useSetGroupingVerified } from 'data-services/hooks/occurrences/track/useSetGroupingVerified'
import {
  MERGE_SCOPES,
  MergeScopeKey,
  useMergeCandidates,
} from 'data-services/hooks/occurrences/useMergeCandidates'
import { isMergeable } from 'data-services/models/merge-candidate'
import { OccurrenceDetails } from 'data-services/models/occurrence-details'
import { GitMergeIcon, Loader2Icon, PlusIcon } from 'lucide-react'
import { Badge, Button, buttonVariants } from 'nova-ui-kit'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'
import { OccurrencePicker } from 'components/track/occurrence-picker'
import { TrackEditDialog } from 'components/track/track-edit-dialog'

const DEFAULT_SCOPE: MergeScopeKey = 'next'

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
  const [sourceIds, setSourceIds] = useState<string[]>([])
  const [scope, setScope] = useState<MergeScopeKey>(DEFAULT_SCOPE)
  const [showOverlapping, setShowOverlapping] = useState(false)

  const merge = useMergeOccurrences(occurrence.id)
  const {
    setGroupingVerified,
    error: verifyError,
    isLoading: verifyLoading,
  } = useSetGroupingVerified(occurrence.id)

  const mergeScope =
    MERGE_SCOPES.find((option) => option.key === scope) ?? MERGE_SCOPES[0]

  const {
    candidates,
    isLoading: candidatesLoading,
    overlappingCount,
  } = useMergeCandidates({
    captures: mergeScope.captures,
    enabled: mergeOpen,
    minutes: mergeScope.minutes,
    occurrenceId: occurrence.id,
    overlapping: showOverlapping,
    projectId: projectId as string,
  })

  // Extending opens the session view on the track's newest frame, where the next
  // capture is a click away.
  const lastCaptureId = occurrence.frames[0]?.captureId
  const extendRoute =
    occurrence.sessionId && lastCaptureId
      ? getAppRoute({
          to: APP_ROUTES.SESSION_DETAILS({
            projectId: projectId as string,
            sessionId: occurrence.sessionId,
          }),
          filters: { capture: lastCaptureId, extend: occurrence.id },
        })
      : undefined

  const verifiedBy = occurrence.groupingVerifiedBy
  const verifiedAt = occurrence.groupingVerifiedAt
  const verifyErrorMessage = verifyError
    ? parseServerError(verifyError).message
    : undefined

  // A ticked row that turns out to share a capture with the track is never sent.
  const blockedIds = candidates
    .filter((candidate) => !isMergeable(candidate))
    .map((candidate) => candidate.id)
  const mergeIds = sourceIds.filter((id) => !blockedIds.includes(id))

  const toggleSource = (id: string) =>
    setSourceIds((ids) =>
      ids.includes(id) ? ids.filter((other) => other !== id) : [...ids, id]
    )

  const changeScope = (key: MergeScopeKey) => {
    setScope(key)
    setSourceIds([])
  }

  // A ticked row that disappears from the list must not be merged unseen.
  const changeShowOverlapping = (value: boolean) => {
    setShowOverlapping(value)

    if (!value) {
      const hidden = candidates
        .filter((candidate) => candidate.relation === 'overlapping')
        .map((candidate) => candidate.id)
      setSourceIds((ids) => ids.filter((id) => !hidden.includes(id)))
    }
  }

  const closeMerge = () => {
    setMergeOpen(false)
    setSourceIds([])
    merge.reset()
  }

  return (
    <div className="flex flex-col items-center text-center gap-2 px-6 mb-6">
      {occurrence.groupingVerified ? (
        <div className="flex flex-col items-center gap-2">
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
      <div className="flex flex-col items-center gap-2">
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
        {canRestructure && extendRoute ? (
          <Link
            className={buttonVariants({ size: 'small', variant: 'outline' })}
            to={extendRoute}
          >
            <PlusIcon className="w-4 h-4" />
            <span>{translate(STRING.TRACK_EXTEND_IN_SESSION)}</span>
          </Link>
        ) : null}
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
        confirmDisabled={!mergeIds.length}
        confirmLabel={
          mergeIds.length === 1
            ? translate(STRING.TRACK_MERGE_ONE)
            : translate(STRING.TRACK_MERGE_COUNT, { count: mergeIds.length })
        }
        description={translate(STRING.TRACK_MERGE_MANY_DESCRIPTION)}
        error={merge.error}
        isLoading={merge.isLoading}
        isWide
        onConfirm={() => merge.mergeOccurrences(mergeIds)}
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
            description={translate(STRING.TRACK_MERGE_SCOPE_DESCRIPTION, {
              scope: translate(mergeScope.label).toLowerCase(),
            })}
            emptyMessage={translate(STRING.TRACK_NO_MERGE_CANDIDATES_SCOPE)}
            isLoading={candidatesLoading}
            onScopeChange={changeScope}
            onShowOverlappingChange={changeShowOverlapping}
            onToggle={toggleSource}
            overlappingCount={overlappingCount}
            scope={scope}
            selectedIds={sourceIds}
            showOverlapping={showOverlapping}
            title={translate(STRING.TRACK_MERGE_CANDIDATES_TITLE)}
          />
        )}
      </TrackEditDialog>
    </div>
  )
}
