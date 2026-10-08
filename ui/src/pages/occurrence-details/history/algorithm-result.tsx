import { EntityRefValue } from 'components/entity-ref-value/entity-ref-value'
import {
  AlgorithmResultEntry,
  getJobConfigField,
  getJobConfigFields,
  getResultKindLabel,
  getResultPrediction,
  ServerHistoryTaxon,
} from 'data-services/models/occurrence-history'
import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import { FilterIcon, LucideIcon, RulerIcon } from 'lucide-react'
import { BasicTooltip, IdentificationCard } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { getEntityRefLabel } from 'utils/entity-references'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { UserInfo } from 'utils/user/types'
import { HistoryStat, HistoryStats, HistoryTime } from './history-stats'
import { MachinePrediction } from './machine-prediction'

const KIND_ICONS: Record<AlgorithmResultEntry['kind'], LucideIcon> = {
  class_masking: FilterIcon,
  size_filter: RulerIcon,
}

const formatConfigValue = (value: unknown) => {
  if (typeof value === 'boolean') {
    return translate(value ? STRING.YES : STRING.NO)
  }
  if (Array.isArray(value)) {
    return value.join(', ')
  }

  return typeof value === 'object' ? JSON.stringify(value) : `${value}`
}

/** The card's subtitle: for class masking the classifier and species list, otherwise the algorithm's name. */
const getSubTitle = (entry: AlgorithmResultEntry) => {
  if (entry.kind === 'class_masking') {
    const refFor = (key: string) =>
      getJobConfigField(entry.job, key)?.ref ?? undefined
    const classifier = refFor('algorithm_id')

    return translate(STRING.HISTORY_MASKING_SUBTITLE, {
      algorithm: classifier
        ? getEntityRefLabel(classifier)
        : entry.algorithm?.name ?? translate(STRING.VALUE_NOT_AVAILABLE),
      list: getEntityRefLabel(refFor('taxa_list_id')),
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
  const Icon = KIND_ICONS[entry.kind]
  const prediction = getResultPrediction(
    entry,
    occurrence.machinePredictions,
    occurrence.determinationTaxon?.id
  )

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
      const threshold = getJobConfigField(entry.job, 'size_threshold')?.value
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
  getJobConfigFields(entry.job).forEach(({ label, value, ref }) => {
    stats.push({
      label,
      value: ref ? (
        <EntityRefValue projectId={projectId as string} reference={ref} />
      ) : (
        formatConfigValue(value)
      ),
    })
  })
  if (entry.algorithm) {
    stats.push({
      label: translate(STRING.FIELD_LABEL_ALGORITHM),
      value: (
        <EntityRefValue
          projectId={projectId as string}
          reference={{
            type: 'algorithm',
            id: entry.algorithm.id,
            name: entry.algorithm.name,
          }}
        />
      ),
    })
  }
  if (entry.job) {
    stats.push({
      label: translate(STRING.FIELD_LABEL_JOB),
      value: (
        <EntityRefValue
          projectId={projectId as string}
          reference={{ type: 'job', id: entry.job.id, name: entry.job.name }}
        />
      ),
    })
  }

  const header = {
    avatar: <Icon className="w-4 h-4 text-generic-white" />,
    avatarTooltip: translate(STRING.HISTORY_ALGORITHM_RESULT),
    subTitle: getSubTitle(entry),
    title: getResultKindLabel(entry),
  }

  // The run's best new classification, with the classifier's other top predictions and the run's details.
  if (prediction) {
    return (
      <MachinePrediction
        {...header}
        currentUser={currentUser}
        identification={prediction}
        occurrence={occurrence}
        timestamp={entry.timestamp}
      >
        <HistoryStats stats={stats} />
      </MachinePrediction>
    )
  }

  return (
    <div>
      <HistoryTime
        label={getFormatedDateTimeString({ date: new Date(entry.timestamp) })}
      />
      <IdentificationCard
        avatar={
          <BasicTooltip content={header.avatarTooltip}>
            <span className="flex items-center justify-center">
              {header.avatar}
            </span>
          </BasicTooltip>
        }
        subTitle={header.subTitle}
        title={header.title}
      >
        <HistoryStats stats={stats} />
      </IdentificationCard>
    </div>
  )
}
