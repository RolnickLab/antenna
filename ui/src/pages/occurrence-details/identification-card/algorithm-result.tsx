import { TaxonDetails } from 'components/taxon-details/taxon-details'
import {
  AlgorithmResultEntry,
  getJobConfigSummary,
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

/** What to call a result's kind, e.g. "Class masking", for the card and for predictions it superseded. */
export const getResultKindLabel = (entry: AlgorithmResultEntry) =>
  translate(SUBTYPES[entry.subtype].label)

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
    case 'class_masking':
      stats.push({
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
      })
      break
    case 'size_filter':
      stats.push({
        label: translate(STRING.HISTORY_SIZE_THRESHOLD),
        value: entry.payload.size_threshold,
      })
      break
  }
  stats.push({
    label: translate(STRING.HISTORY_DETECTIONS_AFFECTED),
    value: entry.payload.detection_ids.length,
  })
  if (entry.job) {
    const configSummary = getJobConfigSummary(entry.job)
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
    if (configSummary) {
      stats.push({
        label: translate(STRING.HISTORY_JOB_SETTINGS),
        value: <span className="break-all">{configSummary}</span>,
      })
    }
  }

  return (
    <div>
      <HistoryTime
        label={getFormatedDateTimeString({ date: new Date(entry.timestamp) })}
      />
      <IdentificationCard
        avatar={<Icon className="w-4 h-4 text-generic-white" />}
        subTitle={entry.algorithm ? getResultKindLabel(entry) : undefined}
        title={entry.algorithm?.name ?? getResultKindLabel(entry)}
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
