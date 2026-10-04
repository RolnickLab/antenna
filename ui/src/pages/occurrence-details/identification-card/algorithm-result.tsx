import { TaxonDetails } from 'components/taxon-details/taxon-details'
import {
  AlgorithmResultEntry,
  getJobSettings,
  getResultPrediction,
  ServerHistoryTaxon,
} from 'data-services/models/occurrence-history'
import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import { FilterIcon, RulerIcon } from 'lucide-react'
import {
  BasicTooltip,
  IdentificationCard,
  IdentificationDetails,
  IdentificationScore,
} from 'nova-ui-kit'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { getAppRoute } from 'utils/getAppRoute'
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
}

/** Labels for the job settings shown as rows; a setting not listed here shows its raw key. */
const SETTING_LABELS: Partial<Record<string, STRING>> = {
  occurrence_id: STRING.HISTORY_SETTING_OCCURRENCE,
  reweight: STRING.HISTORY_SETTING_REWEIGHT,
  source_image_collection_id: STRING.HISTORY_SETTING_CAPTURE_SET,
}

/** What to call a result's kind, e.g. "Class masking", for the card and for predictions it superseded. */
export const getResultKindLabel = (entry: AlgorithmResultEntry) =>
  translate(SUBTYPES[entry.subtype].label)

const formatSettingValue = (key: string, value: unknown) => {
  if (typeof value === 'boolean') {
    return translate(value ? STRING.YES : STRING.NO)
  }
  if (key.endsWith('_id')) {
    return `#${value}`
  }

  return typeof value === 'object' ? JSON.stringify(value) : `${value}`
}

/** The list's id when only the job's settings name it, e.g. after the list was deleted. */
const getSpeciesListFallback = (entry: AlgorithmResultEntry) => {
  const id = entry.job?.config?.taxa_list_id

  return id !== undefined && id !== null
    ? translate(STRING.HISTORY_SPECIES_LIST_ID, { id: `${id}` })
    : translate(STRING.VALUE_NOT_AVAILABLE)
}

/** The card's subtitle: for class masking the classifier and species list, otherwise the algorithm's name. */
const getSubTitle = (entry: AlgorithmResultEntry) => {
  if (entry.subtype === 'class_masking') {
    return translate(STRING.HISTORY_MASKING_SUBTITLE, {
      algorithm:
        entry.source_algorithm?.name ??
        entry.algorithm?.name ??
        translate(STRING.VALUE_NOT_AVAILABLE),
      list: entry.taxa_list?.name ?? getSpeciesListFallback(entry),
    })
  }

  return entry.algorithm?.name
}

/** A fraction as a percentage with at most one decimal, e.g. 0.0315 reads "3.2%". */
const formatPercent = (fraction: number) =>
  `${Math.round(fraction * 1000) / 10}%`

/** The determination row, left out when there was no determination before or after. */
const getDeterminationStats = (
  before: ServerHistoryTaxon | null,
  after: ServerHistoryTaxon | null
): HistoryStat[] => {
  if (!before && !after) {
    return []
  }

  const notAvailable = translate(STRING.VALUE_NOT_AVAILABLE)
  const value =
    before?.id === after?.id
      ? translate(STRING.HISTORY_DETERMINATION_UNCHANGED, {
          name: after?.name ?? notAvailable,
        })
      : translate(STRING.HISTORY_DETERMINATION_CHANGED, {
          after: after?.name ?? notAvailable,
          before: before?.name ?? notAvailable,
        })

  return [{ label: translate(STRING.HISTORY_DETERMINATION), value }]
}

export const AlgorithmResult = ({
  currentUser,
  entry,
  occurrence,
}: {
  currentUser?: UserInfo
  entry: AlgorithmResultEntry
  occurrence: Occurrence
}) => {
  const { projectId } = useParams()
  const { icon: Icon } = SUBTYPES[entry.subtype]
  const prediction = getResultPrediction(
    entry,
    occurrence.determinationTaxon?.id
  )
  const showAgree = occurrence.userPermissions.includes(UserPermission.Update)

  const stats: HistoryStat[] = getDeterminationStats(
    entry.taxon_before,
    entry.taxon
  )
  switch (entry.subtype) {
    case 'class_masking': {
      // Link only a list that still exists; a deleted one shows its id as plain text.
      if (entry.taxa_list) {
        stats.push({
          label: translate(STRING.HISTORY_SPECIES_LIST),
          value: (
            <Link
              className="underline underline-offset-4"
              to={APP_ROUTES.TAXA_LIST_DETAILS({
                projectId: projectId as string,
                taxaListId: `${entry.taxa_list.id}`,
              })}
            >
              {entry.taxa_list.name}
            </Link>
          ),
        })
      } else if (entry.job?.config?.taxa_list_id != null) {
        stats.push({
          label: translate(STRING.HISTORY_SPECIES_LIST),
          value: translate(STRING.HISTORY_SPECIES_LIST_ID, {
            id: `${entry.job.config.taxa_list_id}`,
          }),
        })
      }
      stats.push({
        label: translate(STRING.HISTORY_EXCLUDED_PROBABILITY),
        value: formatPercent(entry.payload.excluded_probability),
      })
      if (entry.original_taxon) {
        stats.push({
          label: translate(STRING.HISTORY_ORIGINAL_PREDICTION),
          value:
            entry.payload.original_score !== null
              ? `${
                  entry.original_taxon.name
                } (${entry.payload.original_score.toFixed(2)})`
              : entry.original_taxon.name,
        })
      }
      break
    }
    case 'size_filter': {
      const threshold = entry.job?.config?.size_threshold
      stats.push({
        label: translate(STRING.HISTORY_DETECTION_SIZE),
        value:
          typeof threshold === 'number'
            ? translate(STRING.HISTORY_DETECTION_SIZE_WITH_THRESHOLD, {
                size: formatPercent(entry.payload.relative_size),
                threshold: formatPercent(threshold),
              })
            : translate(STRING.HISTORY_DETECTION_SIZE_VALUE, {
                size: formatPercent(entry.payload.relative_size),
              }),
      })
      break
    }
  }
  stats.push({
    label: translate(STRING.HISTORY_DETECTIONS_AFFECTED),
    value: new Set(entry.classifications.map((c) => c.detection_id)).size,
  })
  getJobSettings(entry.job).forEach(({ key, value }) => {
    const label = SETTING_LABELS[key]
    stats.push({
      label: label !== undefined ? translate(label) : key,
      value: formatSettingValue(key, value),
    })
  })
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
        subTitle={getSubTitle(entry)}
        title={getResultKindLabel(entry)}
        titleAddon={
          <HistoryTypeBadge
            label={translate(STRING.HISTORY_ALGORITHM_RESULT)}
          />
        }
      >
        {/* The prediction the run made: its best new classification, which can be agreed with. */}
        {prediction ? (
          <IdentificationDetails
            applied={prediction.applied}
            className="border-border border-t"
          >
            <div className="w-full flex flex-col items-end gap-4">
              <div className="w-full flex items-center gap-4">
                <BasicTooltip
                  content={translate(STRING.MACHINE_PREDICTION_SCORE, {
                    score: `${prediction.score}`,
                  })}
                >
                  <div className="px-1">
                    <IdentificationScore confidenceScore={prediction.score} />
                  </div>
                </BasicTooltip>
                <Link
                  to={getAppRoute({
                    to: APP_ROUTES.TAXON_DETAILS({
                      projectId: projectId as string,
                      taxonId: prediction.taxon.id,
                    }),
                  })}
                >
                  <TaxonDetails compact taxon={prediction.taxon} />
                </Link>
              </div>
              {showAgree && (
                <Agree
                  agreed={
                    currentUser
                      ? occurrence.userAgreed(
                          currentUser.id,
                          prediction.taxon.id
                        )
                      : false
                  }
                  agreeWith={{ predictionId: prediction.id }}
                  applied={prediction.applied}
                  occurrenceId={occurrence.id}
                  taxonId={prediction.taxon.id}
                />
              )}
            </div>
          </IdentificationDetails>
        ) : null}
        <HistoryStats stats={stats} />
      </IdentificationCard>
    </div>
  )
}
