import { CaptureDetection } from 'data-services/models/capture'
import { CONSTANTS } from 'nova-ui-kit/constants'
import { STRING } from 'utils/language'

const BEST_MATCH_COLOR = CONSTANTS.COLORS.success[500]
const UNLIKELY_MATCH_COLOR = CONSTANTS.COLORS.neutral[400]
const GLOW_BLUR_PX = 6
const MAX_GLOW_ALPHA = 0.8
const RIM_COLOR = CONSTANTS.COLORS.neutral[900]
const RIM_SPREAD_PX = 3
const MAX_RIM_ALPHA = 0.5
// Best guess from local data: unrelated boxes scored up to about 0.5, continuations above 0.9.
const GRAY_UNTIL = 0.5
const LIKELY_FROM = 0.8
const POSSIBLE_FROM = 0.6

type Rgb = [number, number, number]

const hexToRgb = (hex: string): Rgb => [
  parseInt(hex.slice(1, 3), 16),
  parseInt(hex.slice(3, 5), 16),
  parseInt(hex.slice(5, 7), 16),
]

const mixRgb = (from: Rgb, to: Rgb, amount: number): Rgb =>
  from.map((channel, index) =>
    Math.round(channel + (to[index] - channel) * amount)
  ) as Rgb

const toCss = ([r, g, b]: Rgb, alpha?: number) =>
  alpha === undefined
    ? `rgb(${r} ${g} ${b})`
    : `rgb(${r} ${g} ${b} / ${alpha.toFixed(2)})`

/**
 * Box outline for a candidate in extend mode: gray up to `GRAY_UNTIL`, then through to
 * emerald for the best match, with a glow that grows with it. No score counts as 0.
 */
export const getMatchBoxStyle = (
  likelihood: number | null
): { outlineColor: string; boxShadow: string } => {
  const amount = Math.min(
    Math.max(((likelihood ?? 0) - GRAY_UNTIL) / (1 - GRAY_UNTIL), 0),
    1
  )
  const color = mixRgb(
    hexToRgb(UNLIKELY_MATCH_COLOR),
    hexToRgb(BEST_MATCH_COLOR),
    amount
  )
  const rim = toCss(hexToRgb(RIM_COLOR), (1 - amount) * MAX_RIM_ALPHA)
  const glow = toCss(color, amount * MAX_GLOW_ALPHA)

  return {
    outlineColor: toCss(color),
    // The rim sits just beyond the 2px outline so a gray box still shows on a light sheet.
    boxShadow: `0 0 0 ${RIM_SPREAD_PX}px ${rim}, 0 0 ${GLOW_BLUR_PX}px ${glow}`,
  }
}

export const getMatchLevel = (likelihood: number): STRING =>
  likelihood >= LIKELY_FROM
    ? STRING.TRACK_MATCH_LIKELY
    : likelihood >= POSSIBLE_FROM
    ? STRING.TRACK_MATCH_POSSIBLE
    : STRING.TRACK_MATCH_UNLIKELY

type SpeciesFields = Pick<
  CaptureDetection,
  'id' | 'label' | 'occurrenceId' | 'scoreLabel'
>

// Without a determination the label is "Unidentified" or the detection id, not a species.
export const isIdentified = (detection: SpeciesFields) =>
  !!detection.occurrenceId && detection.scoreLabel !== undefined

/** Other boxes on the capture identified as the same species as this one. */
export const countSameSpecies = (
  detection: SpeciesFields,
  detections: SpeciesFields[]
): number =>
  isIdentified(detection)
    ? detections.filter(
        (other) =>
          other.id !== detection.id &&
          isIdentified(other) &&
          other.label === detection.label
      ).length
    : 0
