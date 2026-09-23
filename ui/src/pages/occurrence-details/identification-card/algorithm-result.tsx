import {
  AlgorithmResultEntry,
  getFoldedPrediction,
  ServerHistoryTaxon,
} from 'data-services/models/occurrence-history'
import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import { FilterIcon, RouteIcon, RulerIcon } from 'lucide-react'
import { IdentificationCard } from 'nova-ui-kit'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { UserInfo, UserPermission } from 'utils/user/types'
import { Agree } from '../agree/agree'
import {
  HistoryStat,
  HistoryStats,
  HistoryTime,
  HistoryTypeBadge,
} from './history-stats'

const SUBTYPES = {
  class_masking: { icon: FilterIcon, label: STRING.HISTORY_CLASS_MASKING },
  size_filter: { icon: RulerIcon, label: STRING.HISTORY_SIZE_FILTER },
  tracking: { icon: RouteIcon, label: STRING.HISTORY_TRACKING },
}

const getDeterminationLabel = (
  before: ServerHistoryTaxon | null,
  after: ServerHistoryTaxon | null
) => {
  const notAvailable = translate(STRING.VALUE_NOT_AVAILABLE)

  if (before?.id === after?.id) {
    return translate(STRING.HISTORY_DETERMINATION_UNCHANGED, {
      name: after?.name ?? notAvailable,
    })
  }

  return `${before?.name ?? notAvailable} → ${after?.name ?? notAvailable}`
}

export const AlgorithmResult = ({
  currentUser,
  entry,
  occurrence,
  onConfirmed,
}: {
  currentUser?: UserInfo
  entry: AlgorithmResultEntry
  occurrence: Occurrence
  onConfirmed?: (occurrenceId: string) => void
}) => {
  const { projectId } = useParams()
  const { icon: Icon, label } = SUBTYPES[entry.subtype]
  const foldedPrediction = getFoldedPrediction(
    entry,
    occurrence.machinePredictions
  )
  const canAgree =
    !!foldedPrediction &&
    occurrence.userPermissions.includes(UserPermission.Update)

  const stats: HistoryStat[] = foldedPrediction
    ? [
        {
          label: translate(STRING.HISTORY_PREDICTION),
          value: `${
            foldedPrediction.taxon.name
          } (${foldedPrediction.score.toFixed(2)})`,
        },
      ]
    : []
  switch (entry.subtype) {
    case 'tracking':
      stats.push(
        {
          label: translate(STRING.HISTORY_FRAMES_LINKED),
          value: entry.payload.frames_linked,
        },
        {
          label: translate(STRING.HISTORY_OCCURRENCES_MERGED),
          value: entry.payload.occurrences_merged.length,
        }
      )
      break
    case 'class_masking':
      stats.push(
        {
          label: translate(STRING.HISTORY_DETERMINATION),
          value: getDeterminationLabel(entry.taxon_before, entry.taxon),
        },
        {
          label: translate(STRING.HISTORY_SPECIES_LIST),
          value: (
            <Link
              className="underline underline-offset-4"
              to={APP_ROUTES.TAXA_LIST_DETAILS({
                projectId: projectId as string,
                taxaListId: `${entry.payload.taxa_list_id}`,
              })}
            >
              {translate(STRING.HISTORY_SPECIES_LIST_ID, {
                id: `${entry.payload.taxa_list_id}`,
              })}
            </Link>
          ),
        },
        {
          label: translate(STRING.HISTORY_DETECTIONS_AFFECTED),
          value: entry.payload.detection_ids.length,
        }
      )
      break
    case 'size_filter':
      stats.push(
        {
          label: translate(STRING.HISTORY_DETERMINATION),
          value: getDeterminationLabel(entry.taxon_before, entry.taxon),
        },
        {
          label: translate(STRING.HISTORY_SIZE_THRESHOLD),
          value: entry.payload.size_threshold,
        },
        {
          label: translate(STRING.HISTORY_DETECTIONS_AFFECTED),
          value: entry.payload.detection_ids.length,
        }
      )
      break
  }
  if (entry.job) {
    stats.push({
      label: translate(STRING.FIELD_LABEL_JOB),
      value: (
        <Link
          className="underline underline-offset-4"
          to={APP_ROUTES.JOB_DETAILS({
            projectId: projectId as string,
            jobId: `${entry.job.id}`,
          })}
        >
          {entry.job.name}
        </Link>
      ),
    })
  }

  return (
    <div>
      <HistoryTime
        label={getFormatedDateTimeString({ date: new Date(entry.timestamp) })}
      />
      <IdentificationCard
        avatar={<Icon className="w-4 h-4 text-generic-white" />}
        subTitle={entry.algorithm ? translate(label) : undefined}
        title={entry.algorithm?.name ?? translate(label)}
        titleAddon={
          <HistoryTypeBadge
            label={translate(STRING.HISTORY_ALGORITHM_RESULT)}
          />
        }
      >
        <HistoryStats stats={stats} />
        {canAgree && foldedPrediction ? (
          <div className="flex justify-end px-4 pb-4">
            <Agree
              agreed={
                currentUser
                  ? occurrence.userAgreed(
                      currentUser.id,
                      foldedPrediction.taxon.id
                    )
                  : false
              }
              agreeWith={{ predictionId: foldedPrediction.id }}
              applied={foldedPrediction.applied}
              occurrenceId={occurrence.id}
              onSuccess={onConfirmed}
              taxonId={foldedPrediction.taxon.id}
            />
          </div>
        ) : null}
      </IdentificationCard>
    </div>
  )
}
