import { PathFrame } from 'data-services/models/occurrence-path'
import { bboxToPercentCentre, bboxToPercentStyle } from './bbox'
import { getGhostFrame } from './ghost-frame'
import styles from './capture.module.scss'

// Enough neighbouring frames to read the animal's movement, few enough that a long
// occurrence does not smear the capture. The path line runs through every frame
// regardless, since one thin line stays legible.
export const MAX_GHOST_BOXES = 16

const EARLIER_COLOR = '#5193F0'
const LATER_COLOR = '#F2A31F'
const MIN_GHOST_OPACITY = 0.15
const OPACITY_FALLOFF = 0.11
// Direction is carried by the dash as well as the colour, so it survives for a reader
// who cannot separate the two hues. Live detection boxes are always solid.
const LATER_DASH = '3 3'
const EARLIER_DASH = undefined
// A crop needs a floor the stroke falloff does not: a thumbnail at 0.15 cannot be read.
const MIN_CROP_OPACITY = 0.5

interface Ghost {
  color: string
  dash?: string
  frame: PathFrame
  height: number
  id: string
  opacity: number
  width: number
  x: number
  y: number
}

export interface Trail {
  ghosts: Ghost[]
  points: string
  /** Ghost boxes drawn, which the cap can hold below the path's length. */
  shownCount: number
}

const frameBox = (frame: PathFrame) => {
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

/** Turn a path into the boxes and line to draw over the capture being viewed. */
export const buildTrail = (
  path: PathFrame[],
  activeCaptureId?: string
): Trail => {
  const anchor = path.findIndex((frame) => frame.captureId === activeCaptureId)

  const points = path.reduce((collected: string[], frame) => {
    const centre = bboxToPercentCentre(
      frame.bbox,
      frame.captureWidth,
      frame.captureHeight
    )

    if (centre) {
      collected.push(`${centre.x},${centre.y}`)
    }

    return collected
  }, [])

  const ghosts = path.reduce((collected: Ghost[], frame, index) => {
    const box = frameBox(frame)
    const distance = anchor === -1 ? index : Math.abs(index - anchor)

    if (!box || index === anchor || distance > MAX_GHOST_BOXES / 2) {
      return collected
    }

    const earlier = anchor !== -1 && index < anchor

    collected.push({
      color: earlier ? EARLIER_COLOR : LATER_COLOR,
      dash: earlier ? EARLIER_DASH : LATER_DASH,
      ...box,
      frame,
      id: frame.detectionId,
      opacity: Math.max(MIN_GHOST_OPACITY, 1 - distance * OPACITY_FALLOFF),
    })

    return collected
  }, [])

  return {
    ghosts,
    points: points.join(' '),
    // The frame being viewed is drawn by its own live box, so it counts as shown.
    shownCount: ghosts.length + (anchor === -1 ? 0 : 1),
  }
}

/** How strongly a ghost is drawn; a box holding a crop is lifted to a readable floor. */
const ghostOpacity = (ghost: Ghost, showCrops?: boolean) =>
  showCrops && ghost.frame.cropUrl
    ? Math.max(MIN_CROP_OPACITY, ghost.opacity)
    : ghost.opacity

export const CaptureGhostTrail = ({
  onSelectFrame,
  showCrops,
  trail,
}: {
  /** Steps the viewer to the frame a ghost box was measured in, keeping the selection. */
  onSelectFrame: (captureId: string) => void
  showCrops?: boolean
  trail: Trail
}) => (
  <>
    <div className={styles.ghostFrames}>
      {trail.ghosts.map((ghost) => {
        const frame = getGhostFrame(ghost.frame, !!showCrops)

        return (
          <button
            aria-label={frame.label}
            className={styles.ghostFrame}
            key={ghost.id}
            onClick={() => onSelectFrame(frame.captureId)}
            style={{
              height: `${ghost.height}%`,
              left: `${ghost.x}%`,
              top: `${ghost.y}%`,
              width: `${ghost.width}%`,
            }}
            type="button"
          >
            {frame.cropUrl ? (
              <img
                alt=""
                src={frame.cropUrl}
                style={{ opacity: ghostOpacity(ghost, showCrops) }}
              />
            ) : null}
          </button>
        )
      })}
    </div>
    <svg
      className={styles.ghostTrail}
      preserveAspectRatio="none"
      viewBox="0 0 100 100"
    >
      <polyline
        fill="none"
        points={trail.points}
        stroke="#000000"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeOpacity={0.4}
        strokeWidth={4}
        vectorEffect="non-scaling-stroke"
      />
      <polyline
        fill="none"
        points={trail.points}
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
          strokeDasharray={ghost.dash}
          strokeOpacity={ghostOpacity(ghost, showCrops)}
          strokeWidth={1.5}
          vectorEffect="non-scaling-stroke"
          width={ghost.width}
          x={ghost.x}
          y={ghost.y}
        />
      ))}
    </svg>
  </>
)
