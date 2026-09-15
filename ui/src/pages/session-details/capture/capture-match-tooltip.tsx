import classNames from 'classnames'
import { CaptureDetection } from 'data-services/models/capture'
import { CaptureMatch } from 'data-services/models/capture-match'
import {
  getDistanceLabel,
  getSimilarityLabel,
  getWhenLabel,
} from 'data-services/models/merge-candidate'
import {
  ArrowLeftRightIcon,
  BanIcon,
  LucideIcon,
  MinusIcon,
  PlusIcon,
} from 'lucide-react'
import { STRING, translate } from 'utils/language'
import { countSameSpecies, getMatchLevel, isIdentified } from './capture-match'
import {
  ExtendClick,
  ExtendClickIndicator,
  getExtendClickHint,
} from './extend-click'

const INDICATORS: Record<
  ExtendClickIndicator,
  { className: string; Icon: LucideIcon }
> = {
  add: { className: 'bg-success text-success-foreground', Icon: PlusIcon },
  blocked: { className: 'bg-neutral-200 text-neutral-600', Icon: BanIcon },
  remove: {
    className: 'bg-destructive text-destructive-foreground',
    Icon: MinusIcon,
  },
  replace: {
    className: 'bg-warning text-warning-foreground',
    Icon: ArrowLeftRightIcon,
  },
}

const Row = ({ label, value }: { label: string; value: string }) => (
  <>
    <dt className="text-muted-foreground">{label}</dt>
    <dd className="tabular-nums">{value}</dd>
  </>
)

/** A box's identity, how well it matches the track, and what a click on it will do. */
export const CaptureMatchTooltip = ({
  click,
  detection,
  detections,
  isTrackFrame,
  match,
}: {
  click?: ExtendClick
  detection: CaptureDetection
  detections: CaptureDetection[]
  isTrackFrame: boolean
  match?: CaptureMatch
}) => {
  const sameSpecies = countSameSpecies(detection, detections)
  const hint = click ? getExtendClickHint(click) : undefined
  const indicator = hint ? INDICATORS[hint.indicator] : undefined
  const likelihood = match?.likelihood ?? null
  const offset = match?.timeOffsetSeconds ?? null

  return (
    <div className="flex flex-col gap-1.5 max-w-64">
      {isIdentified(detection) ? (
        <div className="flex items-baseline gap-2">
          <span className="font-medium">{detection.label}</span>
          <span className="text-muted-foreground tabular-nums">
            {detection.scoreLabel}
          </span>
        </div>
      ) : (
        <span className="font-medium">
          {translate(STRING.TRACK_FRAME_NO_CLASSIFICATION)}
        </span>
      )}
      {!isTrackFrame ? (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">
          <Row
            label={translate(STRING.TRACK_MATCH_LABEL)}
            value={
              likelihood !== null
                ? translate(STRING.TRACK_MATCH_SCORE, {
                    level: translate(getMatchLevel(likelihood)),
                    percent: Math.round(likelihood * 100),
                  })
                : translate(STRING.VALUE_NOT_AVAILABLE)
            }
          />
          {match?.distance != null ? (
            <Row
              label={translate(STRING.TRACK_COLUMN_DISTANCE)}
              value={getDistanceLabel(match.distance)}
            />
          ) : null}
          {match?.similarity != null ? (
            <Row
              label={translate(STRING.TRACK_COLUMN_SIMILARITY)}
              value={getSimilarityLabel(match.similarity)}
            />
          ) : null}
          {offset !== null && match?.relation !== 'same' ? (
            <Row
              label={translate(STRING.TRACK_COLUMN_WHEN)}
              value={getWhenLabel(offset)}
            />
          ) : null}
        </dl>
      ) : null}
      {sameSpecies > 0 ? (
        <span className="text-muted-foreground">
          {translate(STRING.TRACK_MATCH_SAME_SPECIES, { count: sameSpecies })}
        </span>
      ) : null}
      {hint && indicator ? (
        <div className="flex items-center gap-2 pt-1.5 border-t border-border">
          <span
            aria-hidden
            className={classNames(
              'flex items-center justify-center w-4 h-4 rounded-full shrink-0',
              indicator.className
            )}
          >
            <indicator.Icon className="w-3 h-3" />
          </span>
          <span>{translate(hint.string)}</span>
        </div>
      ) : null}
    </div>
  )
}
