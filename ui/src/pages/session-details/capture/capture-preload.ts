import { THUMBNAIL_WIDTHS, TIER_UPSCALE_TOLERANCE } from './capture-tiers'

/** How many captures ahead of the one on screen each navigation direction warms. */
export const PRELOAD_DEPTH = 2

/**
 * Coarse reading of a pixel demand, for callers that should react to a zoom
 * only when it crosses a thumbnail size and so changes which image the next
 * captures need. A gesture within one size reads the same throughout.
 */
export const demandBand = (demand: number) =>
  Object.values(THUMBNAIL_WIDTHS).filter(
    (width) => demand > width * TIER_UPSCALE_TOLERANCE
  ).length

export interface CaptureNeighbourIds {
  nextCaptureId?: string
  nextCaptureWithDetectionsId?: string | null
  prevCaptureId?: string
  prevCaptureWithDetectionsId?: string | null
}

type Direction = keyof CaptureNeighbourIds

// Reviewers step by detections most of the time, so those neighbours are
// warmed before the plain ones at the same distance.
const DIRECTIONS: Direction[] = [
  'nextCaptureWithDetectionsId',
  'prevCaptureWithDetectionsId',
  'nextCaptureId',
  'prevCaptureId',
]

/**
 * Ids to warm around the capture on screen, nearest step first and without
 * repeats. A direction stops where its next id is unknown, so callers get the
 * step after that only once the step before it has been read.
 */
export const planPreload = ({
  depth = PRELOAD_DEPTH,
  lookup,
  startId,
}: {
  depth?: number
  lookup: (id: string) => CaptureNeighbourIds | undefined
  startId: string
}): string[] => {
  const planned: string[] = []
  const seen = new Set([startId])
  const cursors = new Map<Direction, string | undefined>(
    DIRECTIONS.map((direction) => [direction, startId])
  )

  for (let step = 0; step < depth; step++) {
    DIRECTIONS.forEach((direction) => {
      const cursor = cursors.get(direction)
      const next =
        (cursor ? lookup(cursor)?.[direction] : undefined) ?? undefined
      cursors.set(direction, next)

      if (next && !seen.has(next)) {
        seen.add(next)
        planned.push(next)
      }
    })
  }

  return planned
}
