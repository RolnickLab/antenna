import { useOccurrencePath } from 'data-services/hooks/occurrences/useOccurrencePath'
import { SessionDetails } from 'data-services/models/session-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import { BasicTooltip, CONSTANTS } from 'nova-ui-kit'
import { MouseEvent, useMemo } from 'react'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'
import { dateToValue } from '../utils'
import { buildOccurrenceTimeline } from './occurrence-timeline'

// Green first: the plot's detection spikes are blue, so a blue lane would blend in.
const LANE_COLORS = [
  CONSTANTS.COLORS.success[700],
  CONSTANTS.COLORS.warning[600],
  CONSTANTS.COLORS.alert[700],
  CONSTANTS.COLORS.primary[500],
]

// Each block reaches this far past its outer spikes, so a lone frame stays visible.
const BLOCK_PADDING_PX = 3

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

// A click goes to the frame nearest the pointer; a key press goes to the first frame.
const getClickedCaptureId = (
  frames: { captureId: string; left: number }[],
  event: MouseEvent<HTMLButtonElement>
) => {
  const lane = event.currentTarget.parentElement?.getBoundingClientRect()

  if (!lane || event.detail === 0) {
    return frames[0].captureId
  }

  const pointer = ((event.clientX - lane.left) / lane.width) * 100

  return frames.reduce((nearest, frame) =>
    Math.abs(frame.left - pointer) < Math.abs(nearest.left - pointer)
      ? frame
      : nearest
  ).captureId
}

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

  const blocks = useMemo(() => {
    if (!path) {
      return undefined
    }

    const toPercent = (date: Date) =>
      dateToValue({
        date,
        startDate: session.startDate,
        endDate: session.endDate,
      })
    const formatTime = (date: Date) =>
      getFormatedTimeString({ date, options: { second: true } })

    return buildOccurrenceTimeline(path, timeline).map((span) => {
      const first = span.frames[0]
      const last = span.frames[span.frames.length - 1]

      return {
        frames: span.frames.map((frame) => ({
          captureId: frame.captureId,
          left: toPercent(frame.date),
        })),
        key: first.captureId,
        label:
          span.frames.length === 1
            ? translate(STRING.TIMELINE_OCCURRENCE_FRAME, {
                id: occurrenceId,
                time: formatTime(first.timestamp),
              })
            : translate(STRING.TIMELINE_OCCURRENCE_SPAN, {
                count: String(span.frames.length),
                end: formatTime(last.timestamp),
                id: occurrenceId,
                start: formatTime(first.timestamp),
              }),
        left: toPercent(span.start),
        right: toPercent(span.end),
      }
    })
  }, [path, timeline, session, occurrenceId])

  if (!blocks?.length) {
    return null
  }

  return (
    <div className="relative h-2.5">
      {blocks.map((block) => (
        <BasicTooltip key={block.key} asChild content={block.label}>
          <button
            aria-label={block.label}
            className="absolute inset-y-0 rounded-sm pointer-events-auto transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground"
            onClick={(event) =>
              setActiveCaptureId(getClickedCaptureId(block.frames, event))
            }
            style={{
              backgroundColor: color,
              left: `calc(${block.left}% - ${BLOCK_PADDING_PX}px)`,
              width: `calc(${block.right - block.left}% + ${
                2 * BLOCK_PADDING_PX
              }px)`,
            }}
            type="button"
          />
        </BasicTooltip>
      ))}
    </div>
  )
}
