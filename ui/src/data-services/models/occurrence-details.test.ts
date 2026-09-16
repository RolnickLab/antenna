import {
  FrameLabel,
  frameHasVector,
  getFrameClassification,
  getFrameNames,
  OccurrenceDetails,
  ServerFrameClassification,
} from './occurrence-details'
import { Taxon } from './taxa'

const serverTaxon = (id: string, name: string, rank = 'SPECIES') => ({
  cover_image_url: null,
  id,
  name,
  rank,
})

const MOTH = serverTaxon('11532', 'Moth', 'SUPERFAMILY')
const NOCTUA = serverTaxon('3', 'Noctua pronuba')
const XESTIA = serverTaxon('4', 'Xestia c-nigrum')

const classification = (
  overrides: Partial<ServerFrameClassification> = {}
): ServerFrameClassification => ({
  created_at: '2026-04-29T18:00:00',
  score: 0.5,
  taxon: NOCTUA,
  terminal: true,
  ...overrides,
})

describe('frame classification', () => {
  test('a species-level terminal label wins over a higher-scoring moth filter', () => {
    const picked = getFrameClassification([
      classification({ score: 0.95, taxon: MOTH, terminal: false }),
      classification({ score: 0.12 }),
      classification({ score: 0.4, taxon: XESTIA }),
    ])

    expect(picked?.taxon?.name).toBe('Xestia c-nigrum')
  })

  test('a score tie goes to the most recent classification', () => {
    const older = classification({ created_at: '2026-04-29T18:00:00' })
    const newer = classification({
      created_at: '2026-04-29T18:05:00',
      taxon: XESTIA,
    })

    expect(getFrameClassification([older, newer])).toBe(newer)
    expect(getFrameClassification([newer, older])).toBe(newer)
  })

  test('with no terminal classification, the intermediate one names the frame', () => {
    const picked = getFrameClassification([
      classification({ score: 0.1, taxon: null }),
      classification({ score: 0.8, taxon: MOTH, terminal: false }),
    ])

    expect(picked?.taxon?.name).toBe('Moth')
  })

  test('a frame with no classifications has no label', () => {
    expect(getFrameClassification([])).toBeUndefined()
    expect(getFrameClassification(undefined)).toBeUndefined()
  })
})

describe('frame feature vectors', () => {
  test('one classification with a vector makes the frame comparable', () => {
    expect(
      frameHasVector([
        classification({ has_features: false }),
        classification({ has_features: true }),
      ])
    ).toBe(true)
  })

  test('a frame nothing stored a vector for is marked, even with no classifications', () => {
    expect(frameHasVector([classification({ has_features: false })])).toBe(
      false
    )
    expect(frameHasVector([])).toBe(false)
  })

  test('an unset flag stays unknown, so a payload without it marks nothing', () => {
    expect(
      frameHasVector([classification({ has_features: null })])
    ).toBeUndefined()
    expect(frameHasVector([classification()])).toBeUndefined()
  })
})

describe('frame names', () => {
  test('counts frames per label, most frames first, with the highest score', () => {
    const noctua = new Taxon(NOCTUA)
    const xestia = new Taxon(XESTIA)
    const labels: FrameLabel[] = [
      { score: 0.2, taxon: noctua },
      { score: 0.9, taxon: xestia },
      {},
      { score: 0.6, taxon: noctua },
      {},
      { score: 0.4, taxon: noctua },
    ]

    expect(
      getFrameNames(labels).map(({ frames, scoreMax, taxon }) => [
        taxon?.name,
        frames,
        scoreMax,
      ])
    ).toEqual([
      ['Noctua pronuba', 3, 0.6],
      [undefined, 2, undefined],
      ['Xestia c-nigrum', 1, 0.9],
    ])
  })
})

describe('occurrence details', () => {
  const detection = (id: number, classifications: unknown[]) => ({
    bbox: [0, 0, 10, 10],
    capture: { height: 100, id: id + 100, width: 100 },
    classifications,
    height: null,
    id,
    timestamp: `2026-09-09T02:0${id}:00`,
    url: `https://example.com/${id}.jpg`,
    width: null,
  })

  const occurrence = new OccurrenceDetails({
    created_at: '2026-09-09T02:00:00',
    detection_images: [],
    detections: [
      detection(1, [
        classification({ score: 0.95, taxon: MOTH, terminal: false }),
        classification({ has_features: true, score: 0.12 }),
      ]),
      detection(2, []),
    ],
    detections_count: 2,
    determination: { id: 3, name: 'Noctua pronuba' },
    determination_details: { taxon: NOCTUA },
    first_appearance_timestamp: '2026-09-09T02:00:00',
    id: 12,
    identifications: [],
    predictions: [],
    track_stats: null,
    user_permissions: [],
  })

  test('each frame carries its own label, and the track lists every label', () => {
    expect(occurrence.getDetectionInfo('1').frameLabel).toMatchObject({
      score: 0.12,
      taxon: { name: 'Noctua pronuba' },
    })
    expect(occurrence.getDetectionInfo('2').label).toBe('No classification')
    expect(occurrence.frameNames.map(({ taxon }) => taxon?.name)).toEqual([
      'Noctua pronuba',
      undefined,
    ])
  })

  test('each frame reports whether the payload stored a vector for it', () => {
    expect(occurrence.getDetectionInfo('1').hasVector).toBe(true)
    expect(occurrence.getDetectionInfo('2').hasVector).toBe(false)
  })
})
