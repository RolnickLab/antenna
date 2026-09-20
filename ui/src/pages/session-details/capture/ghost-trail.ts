import { PathFrame } from 'data-services/models/occurrence-path'
import { CONSTANTS } from 'nova-ui-kit/constants'
import { bboxToPercentCentre, bboxToPercentStyle } from './bbox'

// Enough neighbouring frames to read the animal's movement, few enough that a long
// occurrence does not smear the capture. The path line runs through every frame
// regardless, since one thin line stays legible.
export const MAX_GHOST_BOXES = 16

// One colour for every path frame, whether it comes before or after the capture on
// screen. It is not the selection blue: that belongs to the box of the occurrence
// being viewed, and a path frame wearing it read as the live box rather than a past one.
// It is the same amber a low-scoring live box outlines itself in, which the dashes and
// the fade are what separate it from.
export const GHOST_COLOR = CONSTANTS.COLORS.warning[500]

// No path frame is drawn solid. Solid is how the capture on screen looks, and telling
// the two apart is the reason the others fade at all.
const MAX_GHOST_OPACITY = 0.75
// Far frames stay faint enough to read as context, dark enough to still be seen.
const MIN_GHOST_OPACITY = 0.2
const OPACITY_FALLOFF = 0.08

/** One frame of the path drawn over a capture it was not measured in. */
export interface Ghost {
  /** Frames between this one and the capture on screen; the neighbour is 1. */
  distance: number
  frame: PathFrame
  height: number
  id: string
  /** This frame was captured before the one on screen. */
  isEarlier: boolean
  opacity: number
  /** Where the frame sits along the whole track, counted from 1. */
  position: number
  width: number
  x: number
  y: number
  /** Nearer frames stack over further ones, the way onion skins do. */
  zIndex: number
}

export interface Trail {
  ghosts: Ghost[]
  points: string
  /** Ghost boxes drawn, which the cap can hold below the path's length. */
  shownCount: number
  /** Frames in the whole path, which is more than the trail draws. */
  total: number
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
  activeCaptureId?: string,
  /** When the capture on screen holds no frame of the track, the only thing that can say
   * whether a frame comes before or after it is its timestamp. */
  activeTimestamp?: Date | null
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
    // With no frame of the track on the capture being viewed there is nothing to measure
    // from, so the track's own order stands in. It starts at one either way: a distance of
    // zero would draw a frame more solidly than the ceiling allows.
    const distance = anchor === -1 ? index + 1 : Math.abs(index - anchor)

    if (!box || index === anchor || distance > MAX_GHOST_BOXES / 2) {
      return collected
    }

    collected.push({
      ...box,
      distance,
      frame,
      id: frame.detectionId,
      isEarlier:
        anchor !== -1
          ? index < anchor
          : !!activeTimestamp &&
            !!frame.timestamp &&
            frame.timestamp < activeTimestamp,
      opacity: Math.max(
        MIN_GHOST_OPACITY,
        MAX_GHOST_OPACITY - (distance - 1) * OPACITY_FALLOFF
      ),
      position: index + 1,
      zIndex: MAX_GHOST_BOXES - distance,
    })

    return collected
  }, [])

  return {
    ghosts,
    points: points.join(' '),
    // The frame being viewed is drawn by its own live box, so it counts as shown.
    shownCount: ghosts.length + (anchor === -1 ? 0 : 1),
    total: path.length,
  }
}
