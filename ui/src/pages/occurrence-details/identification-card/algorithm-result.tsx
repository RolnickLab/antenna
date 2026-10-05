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
import { Ref } from 'utils/references'
import { UserInfo, UserPermission } from 'utils/user/types'
import { Agree } from '../agree/agree'
import {
  HistoryStat,
  HistoryStats,
  HistoryTime,
  HistoryTypeBadge,
  RefValue,
} from './history-stats'

const KINDS = {
  class_masking: { icon: FilterIcon, label: STRING.HISTORY_CLASS_MASKING },
  size_filter: { icon: RulerIcon, label: STRING.HISTORY_SIZE_FILTER },
}

/** Labels for the job settings shown as rows; a setting not listed here shows its raw key. */
const SETTING_LABELS: Partial<Record<string, STRING>> = {
  algorithm_id: STRING.HISTORY_SETTING_CLASSIFIER,
  occurrence_id: STRING.HISTORY_SETTING_OCCURRENCE,
  reweight: STRING.HISTORY_SETTING_REWEIGHT,
  source_image_collection_id: STRING.HISTORY_SETTING_CAPTURE_SET,
  taxa_list_id: STRING.HISTORY_SPECIES_LIST,
}

/** What to call a result's kind, e.g. "Class masking", for the card and for predictions it superseded. */
export const getResultKindLabel = (entry: AlgorithmResultEntry) =>
  translate(KINDS[entry.kind].label)

const formatSettingValue = (value: unknown) => {
  if (typeof value === 'boolean') {
    return translate(value ? STRING.YES : STRING.NO)
  }

  return typeof value === 'object' ? JSON.stringify(value) : `${value}`
}

/** A reference's name, or its id when the record was deleted. */
const getRefLabel = (reference?: Ref) => {
  if (!reference) {
    return translate(STRING.VALUE_NOT_AVAILABLE)
  }

  return (
    reference.name ??
    translate(STRING.HISTORY_RECORD_ID, { id: `${reference.id}` })
  )
}

/** The card's subtitle: for class masking the classifier and species list, otherwise the algorithm's name. */
const getSubTitle = (entry: AlgorithmResultEntry) => {
  if (entry.kind === 'class_masking') {
    const references = entry.job?.references ?? {}

    return translate(STRING.HISTORY_MASKING_SUBTITLE, {
      algorithm: references.algorithm_id
        ? getRefLabel(references.algorithm_id)
        : entry.algorithm?.name ?? translate(STRING.VALUE_NOT_AVAILABLE),
      list: getRefLabel(references.taxa_list_id),
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
  const { icon: Icon } = KINDS[entry.kind]
  const prediction = getResultPrediction(
    entry,
    occurrence.determinationTaxon?.id
  )
  const showAgree = occurrence.userPermissions.includes(UserPermission.Update)

  const stats: HistoryStat[] = getDeterminationStats(
    entry.determination_before,
    entry.determination_after
  )
  switch (entry.kind) {
    case 'class_masking': {
      stats.push({
        label: translate(STRING.HISTORY_EXCLUDED_PROBABILITY),
        value: formatPercent(entry.data.excluded_probability),
      })
      // The top prediction before masking: what the run's best classification replaced.
      const replaced = entry.classifications.find(
        (c) => c.taxon !== null
      )?.replaced
      if (replaced?.taxon) {
        stats.push({
          label: translate(STRING.HISTORY_ORIGINAL_PREDICTION),
          value:
            replaced.score !== null
              ? `${replaced.taxon.name} (${replaced.score.toFixed(2)})`
              : replaced.taxon.name,
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
                size: formatPercent(entry.data.relative_size),
                threshold: formatPercent(threshold),
              })
            : translate(STRING.HISTORY_DETECTION_SIZE_VALUE, {
                size: formatPercent(entry.data.relative_size),
              }),
      })
      break
    }
  }
  stats.push({
    label: translate(STRING.HISTORY_DETECTIONS_AFFECTED),
    value: new Set(entry.classifications.map((c) => c.detection_id)).size,
  })
  getJobSettings(entry.job).forEach(({ key, value, ref }) => {
    const label = SETTING_LABELS[key]
    stats.push({
      label: label !== undefined ? translate(label) : key,
      value: ref ? (
        <RefValue projectId={projectId as string} reference={ref} />
      ) : (
        formatSettingValue(value)
      ),
    })
  })
  if (entry.job) {
    stats.push({
      label: translate(STRING.FIELD_LABEL_JOB),
      value: (
        <RefValue
          projectId={projectId as string}
          reference={{ type: 'job', id: entry.job.id, name: entry.job.name }}
        />
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
