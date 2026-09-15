import { useOccurrencePath } from 'data-services/hooks/occurrences/useOccurrencePath'
import { SessionDetails } from 'data-services/models/session-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import { BasicTooltip, CONSTANTS } from 'nova-ui-kit'
import { useMemo } from 'react'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'
import { dateToValue } from '../utils'
import { buildOccurrenceTimeline } from './occurrence-timeline'

// Selected boxes share one highlight on the capture, so each lane takes its own colour,
// blue first to match that highlight.
const LANE_COLORS = [
  CONSTANTS.COLORS.secondary[700],
  CONSTANTS.COLORS.alert[700],
  CONSTANTS.COLORS.success[700],
  CONSTANTS.COLORS.warning[700],
  CONSTANTS.COLORS.primary[500],
]

interface OccurrenceTimelineMarkersProps {
  occurrenceIds: string[]
  session: SessionDetails
  setActiveCaptureId: (captureId: string) => void
  timeline: TimelineTick[]
}

/** One lane per occurrence showing the captures it appears in, over the activity plot. */
export const OccurrenceTimelineMarkers = ({
  occurrenceIds,
  ...props
}: OccurrenceTimelineMarkersProps) => (
  <div className="absolute inset-x-0 bottom-3 flex flex-col-reverse gap-0.5 pointer-events-none">
    {occurrenceIds.map((occurrenceId, index) => (
      <OccurrenceLane
        key={occurrenceId}
        color={LANE_COLORS[index % LANE_COLORS.length]}
        occurrenceId={occurrenceId}
        {...props}
      />
    ))}
  </div>
)

const OccurrenceLane = ({
  color,
  occurrenceId,
  session,
  setActiveCaptureId,
  timeline,
}: Omit<OccurrenceTimelineMarkersProps, 'occurrenceIds'> & {
  color: string
  occurrenceId: string
}) => {
  const { path } = useOccurrencePath(occurrenceId, true)

  const marks = useMemo(() => {
    if (!path) {
      return undefined
    }

    const { bars, dots } = buildOccurrenceTimeline(path, timeline)
    const toPercent = (date: Date) =>
      dateToValue({
        date,
        startDate: session.startDate,
        endDate: session.endDate,
      })

    return {
      bars: bars.map((bar) => ({
        key: bar.start.getTime(),
        left: toPercent(bar.start),
        width: toPercent(bar.end) - toPercent(bar.start),
      })),
      dots: dots.map((dot) => ({
        captureId: dot.captureId,
        label: translate(STRING.TIMELINE_OCCURRENCE_FRAME, {
          id: occurrenceId,
          time: getFormatedTimeString({
            date: dot.timestamp,
            options: { second: true },
          }),
        }),
        left: toPercent(dot.date),
      })),
    }
  }, [path, timeline, session, occurrenceId])

  if (!marks?.dots.length) {
    return null
  }

  return (
    <div className="relative h-2.5">
      {marks.bars.map((bar) => (
        <div
          key={bar.key}
          className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full"
          style={{
            backgroundColor: color,
            left: `${bar.left}%`,
            width: `${bar.width}%`,
          }}
        />
      ))}
      {marks.dots.map((dot) => (
        <BasicTooltip key={dot.captureId} asChild content={dot.label}>
          <button
            aria-label={dot.label}
            className="absolute top-0 w-2.5 h-2.5 -translate-x-1/2 rounded-full ring-2 ring-background pointer-events-auto transition-transform hover:scale-125 focus-visible:outline-none focus-visible:ring-foreground"
            onClick={() => setActiveCaptureId(dot.captureId)}
            style={{ backgroundColor: color, left: `${dot.left}%` }}
            type="button"
          />
        </BasicTooltip>
      ))}
    </div>
  )
}
