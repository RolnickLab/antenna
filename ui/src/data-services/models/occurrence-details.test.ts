import {
  convertOccurrenceDetection,
  getDetectionClassification,
  ServerOccurrenceDetection,
  sortDetectionsByTime,
} from './occurrence-details'

const taxon = (id: number, name: string) => ({
  id,
  name,
  rank: 'SPECIES',
  cover_image_url: null,
})

const detection = (
  id: number,
  timestamp: string | null,
  overrides: Partial<ServerOccurrenceDetection> = {}
): ServerOccurrenceDetection => ({
  bbox: [10, 20, 40, 120],
  capture: { id: id * 10, url: `https://example.org/${id}.jpg` },
  classifications: [],
  height: null,
  id,
  timestamp,
  url: `https://example.org/crop-${id}.jpg`,
  width: null,
  ...overrides,
})

describe('occurrence detections', () => {
  test('lists detections by capture time, earliest first, untimed last', () => {
    const sorted = sortDetectionsByTime(
      [
        detection(3, '2026-09-01T22:00:10'),
        detection(1, null),
        detection(2, '2026-09-01T22:00:00'),
        detection(4, '2026-09-01T22:00:10'),
      ].map(convertOccurrenceDetection)
    )

    expect(sorted.map((d) => d.id)).toEqual(['2', '3', '4', '1'])
  })

  test('a terminal classification outranks a higher-scoring intermediate one', () => {
    const picked = getDetectionClassification([
      { score: 0.99, taxon: taxon(1, 'Lepidoptera') as any, terminal: false },
      { score: 0.6, taxon: taxon(2, 'Actias luna') as any, terminal: true },
    ])

    expect(picked?.taxon?.name).toBe('Actias luna')
  })

  test('a detection without a stored crop size takes its bounding box proportions', () => {
    const converted = convertOccurrenceDetection(detection(1, null))

    expect(converted.image).toMatchObject({ width: 30, height: 100 })
    expect(converted.captureId).toBe('10')
    expect(converted.detectionLabel).toEqual({})
  })
})
