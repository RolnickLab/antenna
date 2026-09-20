import { Tooltip } from 'nova-ui-kit'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './capture.module.scss'
import { getGhostFrame } from './ghost-frame'
import { Ghost, GHOST_COLOR, MAX_GHOST_BOXES, Trail } from './ghost-trail'

// A hovered frame comes forward of the other path frames and is drawn in full, which
// is how one is picked out of a stack. It stays under the live boxes all the same.
const HOVERED_GHOST_Z = MAX_GHOST_BOXES + 1
const HOVERED_GHOST_OPACITY = 1

/** Which frame this is, when it was captured, and what clicking it does. */
const GhostReading = ({
  ghost,
  time,
  total,
}: {
  ghost: Ghost
  time: string
  total: number
}) => (
  <div className="flex flex-col items-start gap-1">
    <span className="body-base font-medium">
      {translate(STRING.TRACK_POSITION_FRAME, {
        index: ghost.position,
        total,
      })}
    </span>
    <span className="body-small text-muted-foreground">
      {translate(
        ghost.isEarlier ? STRING.TRACK_GHOST_EARLIER : STRING.TRACK_GHOST_LATER,
        { time }
      )}
    </span>
    <span className="body-small text-muted-foreground">
      {translate(STRING.TRACK_GHOST_HINT)}
    </span>
  </div>
)

export const CaptureGhostTrail = ({
  onSelectFrame,
  showCrops,
  trail,
}: {
  /** Steps the viewer to the frame a ghost box was measured in, keeping the selection. */
  onSelectFrame: (captureId: string) => void
  showCrops?: boolean
  trail: Trail
}) => {
  const [hovered, setHovered] = useState<string>()

  const leave = (id: string) =>
    setHovered((current) => (current === id ? undefined : current))

  return (
    <>
      <div className={styles.ghostFrames}>
        {trail.ghosts.map((ghost) => {
          const frame = getGhostFrame(ghost.frame, !!showCrops)
          const isHovered = hovered === ghost.id

          return (
            <Tooltip.Provider
              delayDuration={0}
              disableHoverableContent
              key={ghost.id}
            >
              <Tooltip.Root open={isHovered}>
                <Tooltip.Trigger asChild>
                  <button
                    aria-label={frame.label}
                    className={styles.ghostFrame}
                    onBlur={() => leave(ghost.id)}
                    onClick={() => onSelectFrame(frame.captureId)}
                    onFocus={() => setHovered(ghost.id)}
                    onMouseEnter={() => setHovered(ghost.id)}
                    onMouseLeave={() => leave(ghost.id)}
                    style={{
                      borderColor: GHOST_COLOR,
                      height: `${ghost.height}%`,
                      left: `${ghost.x}%`,
                      opacity: isHovered
                        ? HOVERED_GHOST_OPACITY
                        : ghost.opacity,
                      top: `${ghost.y}%`,
                      width: `${ghost.width}%`,
                      zIndex: isHovered ? HOVERED_GHOST_Z : ghost.zIndex,
                    }}
                    type="button"
                  >
                    {frame.cropUrl ? <img alt="" src={frame.cropUrl} /> : null}
                  </button>
                </Tooltip.Trigger>
                <Tooltip.Content
                  className="z-[1] p-3 pointer-events-none"
                  collisionPadding={8}
                  side="bottom"
                >
                  <GhostReading
                    ghost={ghost}
                    time={frame.time}
                    total={trail.total}
                  />
                </Tooltip.Content>
              </Tooltip.Root>
            </Tooltip.Provider>
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
      </svg>
    </>
  )
}
