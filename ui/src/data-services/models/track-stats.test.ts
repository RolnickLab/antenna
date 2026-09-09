import {
  convertTrackStats,
  getDurationLabel,
  getIdAgreementLabel,
  getMotionLabel,
  getSizeChangeLabel,
} from './track-stats'

const stats = convertTrackStats({
  distinct_taxa: 1,
  frames: 5,
  id_agreement: 0.8,
  motion: 0.1234,
  size_ratio: 1.5,
})

describe('track stats labels', () => {
  test('a missing payload gives no labels', () => {
    expect(convertTrackStats(null)).toBeUndefined()
    expect(getMotionLabel(undefined)).toBeUndefined()
    expect(getSizeChangeLabel(undefined)).toBeUndefined()
    expect(getIdAgreementLabel(undefined)).toBeUndefined()
  })

  test('motion and size change need at least two frames', () => {
    const single = convertTrackStats({
      distinct_taxa: 1,
      frames: 1,
      id_agreement: 1,
      motion: 0,
      size_ratio: 1,
    })

    expect(getMotionLabel(single)).toBeUndefined()
    expect(getSizeChangeLabel(single)).toBeUndefined()
    expect(getMotionLabel(stats)).toBe('12.3% of frame')
    expect(getSizeChangeLabel(stats)).toBe('×1.50')
  })

  test('agreement mentions the taxa only when more than one', () => {
    expect(getIdAgreementLabel(stats)).toBe('80%')
    expect(getIdAgreementLabel({ ...stats!, distinctTaxa: 3 })).toBe(
      '80% · 3 taxa'
    )
    expect(
      getIdAgreementLabel({ ...stats!, idAgreement: null })
    ).toBeUndefined()
  })

  test('durations read as minutes and seconds, with hours when needed', () => {
    expect(getDurationLabel(null)).toBeUndefined()
    expect(getDurationLabel(0)).toBe('0:00')
    expect(getDurationLabel(65.4)).toBe('1:05')
    expect(getDurationLabel(3725)).toBe('1:02:05')
  })
})
