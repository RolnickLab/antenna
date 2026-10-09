import { ModelRefValue } from 'components/model-ref-value/model-ref-value'
import {
  AlgorithmResultEntry,
  getJobConfigField,
  getJobConfigFields,
  getResultKindLabel,
  getResultPrediction,
  ServerHistoryTaxon,
  TrackingTaxonLabels,
} from 'data-services/models/occurrence-history'
import { OccurrenceDetails as Occurrence } from 'data-services/models/occurrence-details'
import { FilterIcon, LucideIcon, RouteIcon, RulerIcon } from 'lucide-react'
import { BasicTooltip, IdentificationCard } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { getModelRefLabel } from 'utils/model-references'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { UserInfo } from 'utils/user/types'
import { HistoryStat, HistoryStats, HistoryTime } from './history-stats'
import { MachinePrediction } from './machine-prediction'

const KIND_ICONS: Record<AlgorithmResultEntry['kind'], LucideIcon> = {
  class_masking: FilterIcon,
  size_filter: RulerIcon,
  tracking: RouteIcon,
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
        ? getModelRefLabel(classifier)
        : entry.algorithm?.name ?? translate(STRING.VALUE_NOT_AVAILABLE),
      list: getModelRefLabel(refFor('taxa_list_id')),
    })
  }

  return entry.algorithm?.name
}

/** A fraction as a percentage with at most one decimal, e.g. 0.0315 reads "3.2%". */
const formatPercent = (fraction: number) =>
  `${Math.round(fraction * 1000) / 10}%`
/** A score as a percentage, or "not available" when it is missing. */
const formatScore = (score?: number | null) =>
  score === null || score === undefined
    ? translate(STRING.VALUE_NOT_AVAILABLE)
    : formatPercent(score)

/** A span of seconds, e.g. "40 s", "3 min 20 s" or "2 hours 5 min". */
const formatDuration = (seconds: number) => {
  const whole = Math.round(seconds)
  if (whole < 60) {
    return translate(STRING.HISTORY_TRACKING_DURATION_SECONDS, {
      seconds: `${whole}`,
    })
  }
  if (whole < 3600) {
    return translate(STRING.HISTORY_TRACKING_DURATION_MINUTES, {
      minutes: `${Math.floor(whole / 60)}`,
      seconds: `${whole % 60}`,
    })
  }

  return translate(STRING.HISTORY_TRACKING_DURATION_HOURS, {
    hours: `${Math.floor(whole / 3600)}`,
    minutes: `${Math.floor((whole % 3600) / 60)}`,
  })
}

/** Each taxon the labels named, its detections and best score; the name is the copy saved with the result. */
const TaxaNamed = ({
  projectId,
  taxa,
}: {
  projectId: string
  taxa: TrackingTaxonLabels[]
}) => (
  <ul className="flex flex-col gap-1">
    {taxa.map((taxon) => (
      <li key={taxon.taxon_id}>
        <ModelRefValue
          projectId={projectId}
          reference={{ type: 'taxon', id: taxon.taxon_id, name: taxon.name }}
        />{' '}
        <span className="text-muted-foreground">
          {translate(STRING.HISTORY_TRACKING_TAXON_VALUE, {
            count: `${taxon.detection_count}`,
            mean: formatScore(taxon.score_mean),
            score: formatScore(taxon.score_max),
          })}
        </span>
      </li>
    ))}
  </ul>
)

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
    case 'tracking': {
      const { data } = entry
      stats.push(
        {
          label: translate(STRING.HISTORY_TRACKING_DETECTIONS),
          value: data.detection_count,
        },
        ...(data.duration_seconds !== undefined &&
        data.duration_seconds !== null
          ? [
              {
                label: translate(STRING.FIELD_LABEL_DURATION),
                value: formatDuration(data.duration_seconds),
              },
            ]
          : []),
        {
          label: translate(STRING.HISTORY_TRACKING_MOVEMENT),
          value: translate(STRING.HISTORY_TRACKING_MOVEMENT_VALUE, {
            distance: formatPercent(data.motion),
          }),
        },
        {
          label: translate(STRING.HISTORY_TRACKING_PATH_LENGTH),
          value: translate(STRING.HISTORY_TRACKING_MOVEMENT_VALUE, {
            distance: formatPercent(data.path_length),
          }),
        },
        {
          label: translate(STRING.HISTORY_TRACKING_SIZE_CHANGE),
          value: translate(STRING.HISTORY_TRACKING_SIZE_CHANGE_VALUE, {
            ratio: `${Math.round(data.size_change * 100) / 100}`,
          }),
        },
        {
          label: translate(STRING.HISTORY_TRACKING_TAXA),
          value: data.taxa?.length ? (
            <TaxaNamed projectId={projectId as string} taxa={data.taxa} />
          ) : (
            data.distinct_taxa
          ),
        },
        {
          label: translate(STRING.HISTORY_TRACKING_LABEL_AGREEMENT),
          value:
            data.label_agreement !== null
              ? formatPercent(data.label_agreement)
              : translate(STRING.VALUE_NOT_AVAILABLE),
        },
        ...(data.score_mean !== undefined && data.score_mean !== null
          ? [
              {
                label: translate(STRING.HISTORY_TRACKING_SCORE_RANGE),
                value: translate(STRING.HISTORY_TRACKING_SCORE_RANGE_VALUE, {
                  min: formatScore(data.score_min),
                  max: formatScore(data.score_max),
                  mean: formatScore(data.score_mean),
                }),
              },
            ]
          : []),
        {
          label: translate(STRING.HISTORY_TRACKING_MERGED),
          value: data.merged_occurrence_ids.length,
        }
      )
      break
    }
  }
  if (entry.classifications.length) {
    stats.push({
      label: translate(STRING.HISTORY_DETECTIONS_AFFECTED),
      value: new Set(entry.classifications.map((c) => c.detection_id)).size,
    })
  }
  getJobConfigFields(entry.job).forEach(({ label, value, ref }) => {
    stats.push({
      label,
      value: ref ? (
        <ModelRefValue projectId={projectId as string} reference={ref} />
      ) : (
        formatConfigValue(value)
      ),
    })
  })
  if (entry.algorithm) {
    stats.push({
      label: translate(STRING.FIELD_LABEL_ALGORITHM),
      value: (
        <ModelRefValue
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
        <ModelRefValue
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
