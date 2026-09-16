import {
  FrameName,
  GroupingSummary as Summary,
} from 'data-services/models/occurrence-details'
import {
  getDurationLabel,
  getIdAgreementLabel,
  getMotionLabel,
  getSizeChangeLabel,
} from 'data-services/models/track-stats'
import { RouteIcon } from 'lucide-react'
import { BasicTooltip, IdentificationCard } from 'nova-ui-kit'
import { cn } from 'nova-ui-kit/utils'
import { Fragment } from 'react'
import { STRING, translate } from 'utils/language'
import { FrameTaxonName } from '../track/frame-caption'

export const GroupingSummary = ({
  frameNames,
  summary,
}: {
  frameNames: FrameName[]
  summary: Summary
}) => {
  const notAvailable = translate(STRING.VALUE_NOT_AVAILABLE)
  const scores = [summary.scoreMin, summary.scoreMax, summary.scoreMean]
  const frames =
    summary.linkedDetections > 0
      ? `${summary.frames} · ${translate(STRING.TRACK_STAT_LINKED, {
          count: summary.linkedDetections,
        })}`
      : `${summary.frames}`

  const stats: {
    isWarning?: boolean
    label: string
    tooltip?: string
    value: string
  }[] = [
    { label: translate(STRING.TRACK_SUMMARY_FRAMES), value: frames },
    ...(summary.framesWithVectors !== undefined
      ? [
          {
            isWarning: summary.framesWithVectors < summary.frames,
            label: translate(STRING.TRACK_SUMMARY_FRAMES_WITH_VECTORS),
            tooltip: translate(STRING.TRACK_SUMMARY_VECTORS_TOOLTIP),
            value: translate(STRING.VALUE_COUNT_OF_TOTAL, {
              count: summary.framesWithVectors,
              total: summary.frames,
            }),
          },
        ]
      : []),
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
        {stats.map(({ isWarning, label, tooltip, value }) => (
          <Fragment key={label}>
            <span className="text-muted-foreground">
              {tooltip ? (
                <BasicTooltip content={tooltip}>
                  <span className="cursor-default underline decoration-dotted underline-offset-4">
                    {label}
                  </span>
                </BasicTooltip>
              ) : (
                label
              )}
            </span>
            <span
              className={cn(
                'tabular-nums',
                isWarning ? 'text-warning-700' : 'text-foreground'
              )}
            >
              {value}
            </span>
          </Fragment>
        ))}
      </div>
      {frameNames.length ? (
        <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-x-6 gap-y-2 px-4 py-4 border-border border-t body-small">
          <span className="col-span-3 text-muted-foreground">
            {translate(STRING.TRACK_SUMMARY_FRAME_NAMES)}
          </span>
          <span className="text-muted-foreground">
            {translate(STRING.FIELD_LABEL_TAXON)}
          </span>
          <span className="text-muted-foreground text-right">
            {translate(STRING.TRACK_COLUMN_FRAMES)}
          </span>
          <span className="text-muted-foreground text-right">
            {translate(STRING.FIELD_LABEL_BEST_SCORE)}
          </span>
          {frameNames.map(({ frames, scoreMax, taxon }) => (
            <Fragment key={taxon?.id ?? ''}>
              <FrameTaxonName taxon={taxon} />
              <span className="text-foreground text-right tabular-nums">
                {frames}
              </span>
              <span className="text-foreground text-right tabular-nums">
                {scoreMax?.toFixed(2) ?? notAvailable}
              </span>
            </Fragment>
          ))}
        </div>
      ) : null}
    </IdentificationCard>
  )
}
