import { GroupingSummary as Summary } from 'data-services/models/occurrence-details'
import {
  getDurationLabel,
  getIdAgreementLabel,
  getMotionLabel,
  getSizeChangeLabel,
} from 'data-services/models/track-stats'
import { RouteIcon } from 'lucide-react'
import { BasicTooltip, IdentificationCard } from 'nova-ui-kit'
import { Fragment } from 'react'
import { STRING, translate } from 'utils/language'

export const GroupingSummary = ({ summary }: { summary: Summary }) => {
  const notAvailable = translate(STRING.VALUE_NOT_AVAILABLE)
  const scores = [summary.scoreMin, summary.scoreMax, summary.scoreMean]
  const frames =
    summary.linkedDetections > 0
      ? `${summary.frames} · ${translate(STRING.TRACK_STAT_LINKED, {
          count: summary.linkedDetections,
        })}`
      : `${summary.frames}`

  const stats = [
    { label: translate(STRING.TRACK_SUMMARY_FRAMES), value: frames },
    {
      label: translate(STRING.FIELD_LABEL_DURATION),
      value: getDurationLabel(summary.durationSeconds) ?? notAvailable,
    },
    {
      label: translate(STRING.FIELD_LABEL_MOTION),
      value: getMotionLabel(summary) ?? notAvailable,
    },
    {
      label: translate(STRING.FIELD_LABEL_SIZE_CHANGE),
      value: getSizeChangeLabel(summary) ?? notAvailable,
    },
    {
      label: translate(STRING.TRACK_SUMMARY_ID_AGREEMENT),
      value: getIdAgreementLabel(summary) ?? notAvailable,
    },
    {
      label: translate(STRING.TRACK_SUMMARY_SCORE_RANGE),
      value: scores.every((score) => typeof score === 'number')
        ? translate(STRING.TRACK_STAT_SCORE_RANGE, {
            max: summary.scoreMax.toFixed(2),
            mean: summary.scoreMean.toFixed(2),
            min: summary.scoreMin.toFixed(2),
          })
        : notAvailable,
    },
  ]

  return (
    <IdentificationCard
      avatar={<RouteIcon className="w-4 h-4 text-generic-white" />}
      title={summary.algorithm?.name ?? translate(STRING.TRACK_SUMMARY_TITLE)}
      titleAddon={
        <BasicTooltip content={translate(STRING.TRACK_SUMMARY_DERIVED_TOOLTIP)}>
          <span className="px-2 py-0.5 rounded-full border border-border body-small text-muted-foreground cursor-default">
            {translate(STRING.TRACK_SUMMARY_DERIVED)}
          </span>
        </BasicTooltip>
      }
    >
      <div className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 px-4 py-4 border-border border-t body-small">
        {stats.map(({ label, value }) => (
          <Fragment key={label}>
            <span className="text-muted-foreground">{label}</span>
            <span className="text-foreground tabular-nums">{value}</span>
          </Fragment>
        ))}
      </div>
    </IdentificationCard>
  )
}
