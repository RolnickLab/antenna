import { OccurrenceTrail } from 'data-services/hooks/occurrences/useOccurrenceTrails'
import { TrackFrame } from 'data-services/models/occurrence-details'
import { useMemo } from 'react'
import { bboxToPercentCentre, bboxToPercentStyle } from './bbox'
import styles from './capture.module.scss'

// Enough neighbouring frames to read the animal's movement, few enough that a
// long occurrence does not smear the capture. The path is drawn through every
// frame regardless, since one thin line stays legible.
const MAX_GHOST_BOXES = 16

const EARLIER_COLOR = '#5193F0'
const LATER_COLOR = '#F2A31F'
const MIN_GHOST_OPACITY = 0.15
const OPACITY_FALLOFF = 0.11
// Every live detection box is a solid outline, so a dash is what says "the animal
// was here in another frame" rather than "there is a detection here".
const GHOST_DASH = '3 3'

interface Ghost {
  color: string
  height: number
  id: string
  opacity: number
  width: number
  x: number
  y: number
}

const frameCentre = (frame: TrackFrame) =>
  bboxToPercentCentre(frame.bbox, frame.captureWidth, frame.captureHeight)

const frameBox = (frame: TrackFrame) => {
  const style = bboxToPercentStyle(
    frame.bbox,
    frame.captureWidth,
    frame.captureHeight
  )

  return style
    ? {
        height: parseFloat(style.height),
        width: parseFloat(style.width),
        x: parseFloat(style.left),
        y: parseFloat(style.top),
      }
    : undefined
}

const buildTrail = (trail: OccurrenceTrail, activeCaptureId?: string) => {
  const anchor = trail.frames.findIndex(
    (frame) => frame.captureId === activeCaptureId
  )
  const path = trail.frames.reduce((points: string[], frame) => {
    const centre = frameCentre(frame)

    if (centre) {
      points.push(`${centre.x},${centre.y}`)
    }

    return points
  }, [])

  const ghosts = trail.frames.reduce((collected: Ghost[], frame, index) => {
    const box = frameBox(frame)
    const distance = anchor === -1 ? index : Math.abs(index - anchor)

    if (!box || index === anchor || distance > MAX_GHOST_BOXES / 2) {
      return collected
    }

    collected.push({
      color: anchor !== -1 && index < anchor ? EARLIER_COLOR : LATER_COLOR,
      ...box,
      id: frame.id,
      opacity: Math.max(MIN_GHOST_OPACITY, 1 - distance * OPACITY_FALLOFF),
    })

    return collected
  }, [])

  return { ghosts, path: path.join(' ') }
}

export const CaptureGhostTrail = ({
  activeCaptureId,
  trails,
}: {
  activeCaptureId?: string
  trails: OccurrenceTrail[]
}) => {
  const built = useMemo(
    () =>
      trails.map((trail) => ({
        occurrenceId: trail.occurrenceId,
        ...buildTrail(trail, activeCaptureId),
      })),
    [trails, activeCaptureId]
  )

  return (
    <svg
      className={styles.ghostTrail}
      preserveAspectRatio="none"
      viewBox="0 0 100 100"
    >
      {built.map((trail) => (
        <g key={trail.occurrenceId}>
          <polyline
            fill="none"
            points={trail.path}
            stroke="#000000"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeOpacity={0.4}
            strokeWidth={4}
            vectorEffect="non-scaling-stroke"
          />
          <polyline
            fill="none"
            points={trail.path}
            stroke="#FFFFFF"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            vectorEffect="non-scaling-stroke"
          />
          {trail.ghosts.map((ghost) => (
            <rect
              fill="none"
              height={ghost.height}
              key={ghost.id}
              rx={0.4}
              stroke={ghost.color}
              strokeDasharray={GHOST_DASH}
              strokeOpacity={ghost.opacity}
              strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
              width={ghost.width}
              x={ghost.x}
              y={ghost.y}
            />
          ))}
        </g>
      ))}
    </svg>
  )
}
