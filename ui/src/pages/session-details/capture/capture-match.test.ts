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

const scored = (likelihood: number | null) => ({
  likelihood,
  skippedReason: null,
  wouldLink: false,
})

describe('getMatchBoxStyle', () => {
  test('the top of the ramp is the palette emerald with the strongest glow and no rim', () => {
    const style = getMatchBoxStyle(scored(0.6))

    expect(style.outlineColor).toBe(rgbOf(CONSTANTS.COLORS.success[500]))
    expect(style.boxShadow).toBe(
      '0 0 0 3px rgb(23 24 32 / 0.00), 0 0 6px rgb(0 174 135 / 0.80)'
    )
  })

  test('the bottom of the ramp is the palette gray with a dark rim and no glow', () => {
    const style = getMatchBoxStyle(scored(0.2))

    expect(style.outlineColor).toBe(rgbOf(CONSTANTS.COLORS.neutral[400]))
    expect(style.boxShadow).toBe(
      '0 0 0 3px rgb(23 24 32 / 0.50), 0 0 6px rgb(159 162 171 / 0.00)'
    )
  })

  test('a likelihood a quarter up the ramp is a quarter of the way from gray to emerald', () => {
    // neutral-400 #9FA2AB towards success-500 #00AE87, channel by channel.
    expect(getMatchBoxStyle(scored(0.3)).outlineColor).toBe('rgb(119 165 162)')
  })

  test('likelihoods beyond either end of the ramp keep its end colours', () => {
    expect(getMatchBoxStyle(scored(0.05))).toEqual(
      getMatchBoxStyle(scored(0.2))
    )
    expect(getMatchBoxStyle(scored(0.95))).toEqual(
      getMatchBoxStyle(scored(0.6))
    )
  })

  test('a box without a score looks like an unlikely match', () => {
    expect(getMatchBoxStyle(scored(null))).toEqual(
      getMatchBoxStyle(scored(0.2))
    )
    expect(getMatchBoxStyle(undefined)).toEqual(getMatchBoxStyle(scored(0.2)))
  })

  test("the tracker's pick gets a second emerald ring and a stronger glow", () => {
    const style = getMatchBoxStyle({
      likelihood: 0.7,
      skippedReason: null,
      wouldLink: true,
    })

    expect(style.outlineColor).toBe(rgbOf(CONSTANTS.COLORS.success[500]))
    expect(style.boxShadow).toBe(
      '0 0 0 4px rgb(23 24 32 / 0.50), 0 0 0 6px rgb(0 174 135), 0 0 12px rgb(0 174 135 / 0.80)'
    )
  })

  test('a box the tracker would skip is dotted gray, however well it scores', () => {
    expect(
      getMatchBoxStyle({
        likelihood: 0.9,
        skippedReason: 'no_vector',
        wouldLink: false,
      })
    ).toEqual({
      outlineColor: rgbOf(CONSTANTS.COLORS.neutral[400]),
      outlineStyle: 'dotted',
      boxShadow: '0 0 0 3px rgb(23 24 32 / 0.50)',
    })
  })
})

describe('getMatchLevel', () => {
  test('names the likelihood by the tracker threshold (0.5) and twice its cost (1/3)', () => {
    expect(getMatchLevel(0.5)).toBe(STRING.TRACK_MATCH_LIKELY)
    expect(getMatchLevel(0.4)).toBe(STRING.TRACK_MATCH_POSSIBLE)
    expect(getMatchLevel(0.3)).toBe(STRING.TRACK_MATCH_UNLIKELY)
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
