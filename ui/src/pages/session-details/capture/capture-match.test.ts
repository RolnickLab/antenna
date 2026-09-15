import { CaptureMatch } from 'data-services/models/capture-match'
import { CONSTANTS } from 'nova-ui-kit/constants'
import { STRING } from 'utils/language'
import {
  countSameSpecies,
  getMatchBoxStyle,
  getMatchLevel,
  getMatchNotes,
} from './capture-match'

type MatchFields = Pick<
  CaptureMatch,
  'likelihood' | 'relation' | 'skippedReason' | 'wouldLink'
>

const match = (fields: Partial<MatchFields> = {}): MatchFields => ({
  likelihood: null,
  relation: 'after',
  skippedReason: null,
  wouldLink: false,
  ...fields,
})

const rgbOf = (hex: string) =>
  `rgb(${parseInt(hex.slice(1, 3), 16)} ${parseInt(
    hex.slice(3, 5),
    16
  )} ${parseInt(hex.slice(5, 7), 16)})`

describe('getMatchBoxStyle', () => {
  test('the best match is the palette emerald with the strongest glow and no rim', () => {
    const style = getMatchBoxStyle(match({ likelihood: 1 }))

    expect(style.outlineColor).toBe(rgbOf(CONSTANTS.COLORS.success[500]))
    expect(style.boxShadow).toBe(
      '0 0 0 3px rgb(23 24 32 / 0.00), 0 0 6px rgb(0 174 135 / 0.80)'
    )
  })

  test('an unlikely match is the palette gray with a dark rim and no glow', () => {
    const style = getMatchBoxStyle(match({ likelihood: 0.5 }))

    expect(style.outlineColor).toBe(rgbOf(CONSTANTS.COLORS.neutral[400]))
    expect(style.boxShadow).toBe(
      '0 0 0 3px rgb(23 24 32 / 0.50), 0 0 6px rgb(159 162 171 / 0.00)'
    )
  })

  test('a likelihood a quarter of the way from the gray floor to 1 is a quarter of the way to emerald', () => {
    // neutral-400 #9FA2AB towards success-500 #00AE87, channel by channel.
    expect(getMatchBoxStyle(match({ likelihood: 0.625 })).outlineColor).toBe(
      'rgb(119 165 162)'
    )
  })

  test('a likelihood below the floor or above 1 keeps the end colours', () => {
    expect(getMatchBoxStyle(match({ likelihood: 0.3 }))).toEqual(
      getMatchBoxStyle(match({ likelihood: 0.5 }))
    )
    expect(getMatchBoxStyle(match({ likelihood: 1.4 }))).toEqual(
      getMatchBoxStyle(match({ likelihood: 1 }))
    )
  })

  test('a box without a score looks like an unlikely match', () => {
    const unlikely = getMatchBoxStyle(match({ likelihood: 0.5 }))

    expect(getMatchBoxStyle(match())).toEqual(unlikely)
    expect(getMatchBoxStyle(undefined)).toEqual(unlikely)
  })

  test("the tracker's pick gets a second emerald ring and a stronger glow", () => {
    const pick = getMatchBoxStyle(match({ likelihood: 0.95, wouldLink: true }))

    expect(pick.outlineColor).toBe(rgbOf(CONSTANTS.COLORS.success[500]))
    expect(pick.boxShadow).toBe(
      '0 0 0 4px rgb(23 24 32 / 0.50), 0 0 0 6px rgb(0 174 135), 0 0 12px rgb(0 174 135 / 0.80)'
    )
    expect(pick).not.toEqual(getMatchBoxStyle(match({ likelihood: 0.95 })))
  })

  test('a box the tracker would skip is dotted gray, however well it scores', () => {
    expect(
      getMatchBoxStyle(match({ likelihood: 0.95, skippedReason: 'no_vector' }))
    ).toEqual({
      outlineColor: rgbOf(CONSTANTS.COLORS.neutral[400]),
      outlineStyle: 'dotted',
      boxShadow: '0 0 0 3px rgb(23 24 32 / 0.50)',
    })
  })
})

describe('getMatchLevel', () => {
  test('names the likelihood in three bands', () => {
    expect(getMatchLevel(0.9)).toBe(STRING.TRACK_MATCH_LIKELY)
    expect(getMatchLevel(0.7)).toBe(STRING.TRACK_MATCH_POSSIBLE)
    expect(getMatchLevel(0.5)).toBe(STRING.TRACK_MATCH_UNLIKELY)
  })
})

describe('getMatchNotes', () => {
  test("the tracker's pick says automatic tracking would link it", () => {
    expect(getMatchNotes(match({ likelihood: 0.95, wouldLink: true }))).toEqual(
      [{ isEmphasis: true, string: STRING.TRACK_MATCH_WOULD_LINK }]
    )
  })

  test('a box on a capture inside a gap of the track is marked as a preview', () => {
    expect(getMatchNotes(match({ likelihood: 0.7, relation: 'gap' }))).toEqual([
      { isEmphasis: false, string: STRING.TRACK_MATCH_GAP_NOTE },
    ])
  })

  test('a box without a feature vector says tracking would skip it', () => {
    expect(
      getMatchNotes(match({ likelihood: 0.7, skippedReason: 'no_vector' }))
    ).toEqual([
      { isEmphasis: false, string: STRING.TRACK_MATCH_SKIPPED_NO_VECTOR },
    ])
  })

  test('an ordinary candidate beside the track has no notes', () => {
    expect(getMatchNotes(match({ likelihood: 0.7 }))).toEqual([])
    expect(getMatchNotes(undefined)).toEqual([])
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
