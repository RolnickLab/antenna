import { hasProjectFeature, withoutTrackingColumns } from './project-features'

describe('hasProjectFeature', () => {
  test('is on only when the flag is true', () => {
    expect(hasProjectFeature({ tracking: true }, 'tracking')).toBe(true)
    expect(hasProjectFeature({ tracking: false }, 'tracking')).toBe(false)
    expect(hasProjectFeature({ tags: true }, 'tracking')).toBe(false)
  })

  test('is off while the project has not loaded', () => {
    expect(hasProjectFeature(undefined, 'tracking')).toBe(false)
    expect(hasProjectFeature({}, 'tracking')).toBe(false)
  })
})

describe('withoutTrackingColumns', () => {
  const columns = [
    { id: 'id' },
    { id: 'detections' },
    { id: 'duration' },
    { id: 'motion' },
    { id: 'size-change' },
    { id: 'id-agreement' },
  ]

  test('drops the track statistic columns when tracking is off', () => {
    expect(withoutTrackingColumns(columns, false).map((c) => c.id)).toEqual([
      'id',
      'duration',
    ])
  })

  test('keeps every column when tracking is on', () => {
    expect(withoutTrackingColumns(columns, true)).toEqual(columns)
  })
})
