import {
  ComparisonSide,
  ComparisonSides,
  getCostLabel,
  getDistanceLabel,
  getLikelihoodLabel,
  getRatioLabel,
  getSimilarityLabel,
  MergeCandidate,
} from 'data-services/models/merge-candidate'
import { ArrowRightIcon, CheckIcon } from 'lucide-react'
import { CSSProperties } from 'react'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'

export const COMPARISON_PANEL_WIDTH = 400
export const COMPARISON_PANEL_HEIGHT = 330

export type ComparisonScores = Pick<
  MergeCandidate,
  | 'displayName'
  | 'distance'
  | 'similarity'
  | 'cost'
  | 'iou'
  | 'sizeRatio'
  | 'likelihood'
  | 'wouldLink'
>

const Crop = ({ side, size }: { side: ComparisonSide; size: string }) => (
  <div className="flex flex-col items-center gap-1">
    <div className={`${size} bg-muted rounded-md overflow-hidden`}>
      {side.src ? (
        <img alt="" className="w-full h-full object-contain" src={side.src} />
      ) : null}
    </div>
    <span className="body-small text-muted-foreground tabular-nums">
      {side.timestamp
        ? getFormatedTimeString({
            date: side.timestamp,
            options: { second: true },
          })
        : translate(STRING.VALUE_NOT_AVAILABLE)}
    </span>
  </div>
)

const Metric = ({ label, value }: { label: STRING; value: string }) => (
  <span className="inline-flex items-center gap-1 whitespace-nowrap">
    <span className="text-muted-foreground">{translate(label)}</span>
    <span className="tabular-nums">{value}</span>
  </span>
)

/**
 * Hover preview of one scored pair: the earlier crop on the left, the later on the
 * right, every term of the tracking cost, and the tracker's own verdict on the pair.
 * Decorative, so it never takes the pointer.
 */
export const CandidateComparison = ({
  candidate,
  costThreshold,
  requiresFeatures,
  sides,
  style,
}: {
  candidate: ComparisonScores
  /** Tracking links a pair only under this cost. */
  costThreshold?: number
  /** Tracking skips a pair with no vector on both sides instead of matching it on geometry. */
  requiresFeatures?: boolean
  sides: ComparisonSides
  style: CSSProperties
}) => {
  const paired = sides.left.src && sides.right.src
  const single = sides.left.src ? sides.left : sides.right
  const verdict = candidate.wouldLink
    ? STRING.TRACK_MATCH_WOULD_LINK
    : requiresFeatures && candidate.similarity === null
    ? STRING.TRACK_MATCH_SKIPPED_NO_VECTOR
    : undefined

  return (
    <div
      aria-hidden
      className="fixed z-[60] pointer-events-none flex flex-col gap-2 p-3 rounded-md border border-border bg-background shadow-md"
      style={{ width: COMPARISON_PANEL_WIDTH, ...style }}
    >
      <span className="body-small font-medium truncate">
        {candidate.displayName}
      </span>
      {paired ? (
        <div className="flex items-center justify-between gap-3">
          <Crop side={sides.left} size="w-40 h-40" />
          <ArrowRightIcon
            aria-hidden
            className="w-4 h-4 text-muted-foreground"
          />
          <Crop side={sides.right} size="w-40 h-40" />
        </div>
      ) : (
        <div className="flex justify-center">
          <Crop side={single} size="w-48 h-48" />
        </div>
      )}
      <div className="flex items-center justify-center gap-4 body-small">
        <Metric label={STRING.TRACK_COLUMN_WHEN} value={sides.gapLabel} />
        <Metric
          label={STRING.TRACK_COLUMN_DISTANCE}
          value={getDistanceLabel(candidate.distance)}
        />
        <Metric
          label={STRING.TRACK_COLUMN_SIMILARITY}
          value={getSimilarityLabel(candidate.similarity)}
        />
      </div>
      <div className="flex items-center justify-center gap-4 body-small">
        <Metric
          label={STRING.TRACK_COLUMN_OVERLAP}
          value={getRatioLabel(candidate.iou)}
        />
        <Metric
          label={STRING.TRACK_COLUMN_SIZE}
          value={getRatioLabel(candidate.sizeRatio)}
        />
        <Metric
          label={STRING.TRACK_COLUMN_COST}
          value={getCostLabel(candidate.cost, costThreshold)}
        />
      </div>
      <div className="flex items-center justify-center gap-2 body-small">
        <Metric
          label={STRING.TRACK_COLUMN_MATCH}
          value={getLikelihoodLabel(candidate.likelihood)}
        />
        {verdict ? (
          <span className="inline-flex items-center gap-1 text-muted-foreground">
            {candidate.wouldLink ? (
              <CheckIcon aria-hidden className="w-3 h-3 text-success" />
            ) : null}
            {translate(verdict)}
          </span>
        ) : null}
      </div>
    </div>
  )
}
