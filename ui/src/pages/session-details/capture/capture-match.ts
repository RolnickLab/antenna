import { CaptureDetection } from 'data-services/models/capture'
import { CaptureMatch } from 'data-services/models/capture-match'
import { CONSTANTS } from 'nova-ui-kit/constants'
import { STRING } from 'utils/language'

const BEST_MATCH_COLOR = CONSTANTS.COLORS.success[500]
const UNLIKELY_MATCH_COLOR = CONSTANTS.COLORS.neutral[400]
const GLOW_BLUR_PX = 6
const LIKELY_GLOW_BLUR_PX = 10
const MAX_GLOW_ALPHA = 0.8
const RIM_COLOR = CONSTANTS.COLORS.neutral[900]
const RIM_SPREAD_PX = 3
const MAX_RIM_ALPHA = 0.5
const LINK_GAP_PX = 4
const LINK_RING_PX = 6
const LINK_GLOW_PX = 12
// Best guess from local data: unrelated boxes scored up to about 0.5, continuations above 0.9.
const GRAY_UNTIL = 0.5
const LIKELY_FROM = 0.8
const POSSIBLE_FROM = 0.6
// How far from gray to emerald each band starts, so a Possible box already reads green.
const COLOR_STOPS: [likelihood: number, amount: number][] = [
  [GRAY_UNTIL, 0],
  [POSSIBLE_FROM, 0.5],
  [LIKELY_FROM, 0.85],
  [1, 1],
]

type Rgb = [number, number, number]

const greenAmount = (likelihood: number): number => {
  const clamped = Math.min(Math.max(likelihood, GRAY_UNTIL), 1)
  const index = COLOR_STOPS.findIndex(([stop]) => clamped <= stop)
  if (index <= 0) return 0
  const [fromStop, fromAmount] = COLOR_STOPS[index - 1]
  const [toStop, toAmount] = COLOR_STOPS[index]
  return (
    fromAmount +
    ((clamped - fromStop) / (toStop - fromStop)) * (toAmount - fromAmount)
  )
}

type MatchFields = Pick<
  CaptureMatch,
  | 'likelihood'
  | 'referenceCaptureOffset'
  | 'skippedReason'
  | 'skipsSession'
  | 'wouldLink'
>

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
 * emerald for the best match, with a wider glow from the Likely band up. The tracker's own
 * pick gets a second ring and a stronger glow, and a box it would skip keeps its colour with
 * a dotted outline. No score counts as 0.
 */
export const getMatchBoxStyle = (
  match?: Omit<MatchFields, 'referenceCaptureOffset'>
): { outlineColor: string; outlineStyle?: 'dotted'; boxShadow: string } => {
  const gray = hexToRgb(UNLIKELY_MATCH_COLOR)
  const green = hexToRgb(BEST_MATCH_COLOR)
  const fullRim = toCss(hexToRgb(RIM_COLOR), MAX_RIM_ALPHA)

  if (match?.wouldLink) {
    return {
      outlineColor: toCss(green),
      boxShadow: `0 0 0 ${LINK_GAP_PX}px ${fullRim}, 0 0 0 ${LINK_RING_PX}px ${toCss(
        green
      )}, 0 0 ${LINK_GLOW_PX}px ${toCss(green, MAX_GLOW_ALPHA)}`,
    }
  }

  const likelihood = match?.likelihood ?? 0
  const amount = greenAmount(likelihood)
  const color = mixRgb(gray, green, amount)
  const rim = toCss(hexToRgb(RIM_COLOR), (1 - amount) * MAX_RIM_ALPHA)
  const glow = toCss(color, amount * MAX_GLOW_ALPHA)
  const glowBlur =
    likelihood >= LIKELY_FROM ? LIKELY_GLOW_BLUR_PX : GLOW_BLUR_PX

  return {
    outlineColor: toCss(color),
    ...(match?.skippedReason ? { outlineStyle: 'dotted' as const } : {}),
    // The rim sits just beyond the 2px outline so a gray box still shows on a light sheet.
    boxShadow: `0 0 0 ${RIM_SPREAD_PX}px ${rim}, 0 0 ${glowBlur}px ${glow}`,
  }
}

export const getMatchLevel = (likelihood: number): STRING =>
  likelihood >= LIKELY_FROM
    ? STRING.TRACK_MATCH_LIKELY
    : likelihood >= POSSIBLE_FROM
    ? STRING.TRACK_MATCH_POSSIBLE
    : STRING.TRACK_MATCH_UNLIKELY

/** Lines under a candidate's scores: what the tracker itself would do, and when the preview is only indicative. */
export const getMatchNotes = (
  match?: MatchFields
): { isEmphasis: boolean; string: STRING; values?: { count: number } }[] => {
  const offset = match?.referenceCaptureOffset ?? null

  return [
    ...(match?.wouldLink
      ? [{ isEmphasis: true, string: STRING.TRACK_MATCH_WOULD_LINK }]
      : []),
    ...(offset !== null && Math.abs(offset) > 1
      ? [
          {
            isEmphasis: false,
            string:
              offset > 0
                ? STRING.TRACK_MATCH_REFERENCE_EARLIER
                : STRING.TRACK_MATCH_REFERENCE_LATER,
            values: { count: Math.abs(offset) },
          },
        ]
      : []),
    ...(match?.skippedReason === 'no_vector'
      ? [
          {
            isEmphasis: false,
            string: match.skipsSession
              ? STRING.TRACK_MATCH_SKIPPED_SESSION
              : STRING.TRACK_MATCH_SKIPPED_NO_VECTOR,
          },
        ]
      : []),
  ]
}

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
