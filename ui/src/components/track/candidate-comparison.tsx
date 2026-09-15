import {
  ComparisonSide,
  ComparisonSides,
} from 'data-services/models/merge-candidate'
import { ArrowRightIcon } from 'lucide-react'
import { CSSProperties } from 'react'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'

export const COMPARISON_PANEL_WIDTH = 400
export const COMPARISON_PANEL_HEIGHT = 240

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

/**
 * Hover preview of one scored pair: the earlier crop on the left, the later on
 * the right, the gap between them. Decorative, so it never takes the pointer.
 */
export const CandidateComparison = ({
  displayName,
  sides,
  style,
}: {
  displayName: string
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
          <div className="flex flex-col items-center gap-1 text-muted-foreground">
            <ArrowRightIcon aria-hidden className="w-4 h-4" />
            <span className="body-small tabular-nums whitespace-nowrap">
              {sides.gapLabel}
            </span>
          </div>
          <Crop side={sides.right} size="w-40 h-40" />
        </div>
      ) : (
        <div className="flex justify-center">
          <Crop side={single} size="w-48 h-48" />
        </div>
      )}
    </div>
  )
}
