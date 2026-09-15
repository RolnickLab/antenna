import { CONSTANTS } from 'nova-ui-kit/constants'
import { STRING } from 'utils/language'
import {
  countSameSpecies,
  getMatchBoxStyle,
  getMatchLevel,
} from './capture-match'

const rgbOf = (hex: string) =>
  `rgb(${parseInt(hex.slice(1, 3), 16)} ${parseInt(
    hex.slice(3, 5),
    16
  )} ${parseInt(hex.slice(5, 7), 16)})`

describe('getMatchBoxStyle', () => {
  test('the best match is the palette emerald with the strongest glow', () => {
    const style = getMatchBoxStyle(1)

    expect(style.outlineColor).toBe(rgbOf(CONSTANTS.COLORS.success[500]))
    expect(style.boxShadow).toBe('0 0 6px rgb(0 174 135 / 0.80)')
  })

  test('an unlikely match is the palette gray with no visible glow', () => {
    const style = getMatchBoxStyle(0)

    expect(style.outlineColor).toBe(rgbOf(CONSTANTS.COLORS.neutral[400]))
    expect(style.boxShadow).toBe('0 0 6px rgb(159 162 171 / 0.00)')
  })

  test('a likelihood halfway from the gray floor to 1 sits halfway between the two palette shades', () => {
    // success-500 #00AE87 and neutral-400 #9FA2AB, channel by channel.
    expect(getMatchBoxStyle(0.75).outlineColor).toBe('rgb(80 168 153)')
  })

  test('a likelihood at or below the floor stays gray, however far above 0', () => {
    expect(getMatchBoxStyle(0.5)).toEqual(getMatchBoxStyle(0))
    expect(getMatchBoxStyle(0.3)).toEqual(getMatchBoxStyle(0))
  })

  test('a box without a score is gray and does not glow', () => {
    expect(getMatchBoxStyle(null)).toEqual({
      outlineColor: rgbOf(CONSTANTS.COLORS.neutral[400]),
    })
  })

  test('a likelihood outside 0 to 1 is clamped to the ends of the scale', () => {
    expect(getMatchBoxStyle(1.4)).toEqual(getMatchBoxStyle(1))
    expect(getMatchBoxStyle(-0.2)).toEqual(getMatchBoxStyle(0))
  })
})

describe('getMatchLevel', () => {
  test('names the likelihood in three bands', () => {
    expect(getMatchLevel(0.9)).toBe(STRING.TRACK_MATCH_LIKELY)
    expect(getMatchLevel(0.7)).toBe(STRING.TRACK_MATCH_POSSIBLE)
    expect(getMatchLevel(0.5)).toBe(STRING.TRACK_MATCH_UNLIKELY)
  })
})

describe('countSameSpecies', () => {
  const moth = (id: string, label: string, scoreLabel?: string) => ({
    id,
    label,
    occurrenceId: `o${id}`,
    scoreLabel,
  })

  test('counts the other boxes with the same determination', () => {
    const detections = [
      moth('1', 'Noctua', '0.80'),
      moth('2', 'Noctua', '0.60'),
      moth('3', 'Noctua', '0.70'),
      moth('4', 'Catocala', '0.90'),
    ]

    expect(countSameSpecies(detections[0], detections)).toBe(2)
  })

  test('boxes without a determination are not a species', () => {
    const detections = [
      moth('1', 'Unidentified'),
      moth('2', 'Unidentified'),
      { id: '3', label: '3', occurrenceId: undefined, scoreLabel: '0.00' },
    ]

    expect(countSameSpecies(detections[0], detections)).toBe(0)
    expect(countSameSpecies(detections[2], detections)).toBe(0)
  })
})
