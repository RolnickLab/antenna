import {
  ComparisonSide,
  ComparisonSides,
  getDistanceLabel,
  getSimilarityLabel,
} from 'data-services/models/merge-candidate'
import { ArrowRightIcon } from 'lucide-react'
import { CSSProperties } from 'react'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'

export const COMPARISON_PANEL_WIDTH = 400
export const COMPARISON_PANEL_HEIGHT = 280

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
 * right, and every score the row carries. Decorative, so it never takes the pointer.
 */
export const CandidateComparison = ({
  displayName,
  distance,
  similarity,
  sides,
  style,
}: {
  displayName: string
  distance: number | null
  similarity: number | null
  sides: ComparisonSides
  style: CSSProperties
}) => {
  const paired = sides.left.src && sides.right.src
  const single = sides.left.src ? sides.left : sides.right

  return (
    <div
      aria-hidden
      className="fixed z-[60] pointer-events-none flex flex-col gap-2 p-3 rounded-md border border-border bg-background shadow-md"
      style={{ width: COMPARISON_PANEL_WIDTH, ...style }}
    >
      <span className="body-small font-medium truncate">{displayName}</span>
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
          value={getDistanceLabel(distance)}
        />
        <Metric
          label={STRING.TRACK_COLUMN_SIMILARITY}
          value={getSimilarityLabel(similarity)}
        />
      </div>
    </div>
  )
}
