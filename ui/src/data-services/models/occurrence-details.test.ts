import {
  FrameName,
  formatFrameNames,
  frameHasVector,
  getFrameClassification,
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
  test('reads as one line of names and counts, unclassified frames included', () => {
    const names: FrameName[] = [
      { frames: 2, taxon: new Taxon(NOCTUA) },
      { frames: 1 },
      { frames: 1, taxon: new Taxon(XESTIA) },
    ]

    expect(formatFrameNames(names)).toBe(
      'Noctua pronuba ×2, No classification ×1, Xestia c-nigrum ×1'
    )
    expect(formatFrameNames(names, 1)).toBe('Noctua pronuba ×2, 2 more')
    expect(formatFrameNames([])).toBe('')
  })
})

describe('occurrence details', () => {
  const detection = (id: number, classifications: unknown[]) => ({
    bbox: [0, 0, 10, 20],
    capture: {
      height: 100,
      id: id + 100,
      // Only the first frame's capture has an image stored.
      url: id === 1 ? 'https://example.com/capture-101.jpg' : null,
      width: 100,
    },
    classifications,
    frame_index: id - 1,
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
    detections_count: 40,
    determination: { id: 3, name: 'Noctua pronuba' },
    determination_details: { taxon: NOCTUA },
    first_appearance_timestamp: '2026-09-09T02:00:00',
    first_detection: {
      capture_id: 101,
      frame_index: 0,
      id: 1,
      timestamp: '2026-09-09T02:01:00',
    },
    grouping_summary: {
      frame_names: [
        {
          frames: 30,
          score_max: 0.4,
          taxon: { id: 3, name: 'Noctua pronuba', rank: 'SPECIES' },
        },
        { frames: 10, score_max: null, taxon: null },
      ],
    },
    id: 12,
    identifications: [],
    last_detection: {
      capture_id: 140,
      frame_index: 39,
      id: 40,
      timestamp: '2026-09-09T02:40:00',
    },
    predictions: [],
    track_stats: null,
    user_permissions: [],
  })

  test('each frame of the first page carries its own label and position', () => {
    const [first, second] = occurrence.firstFramesPage

    expect(first).toMatchObject({
      captureId: '101',
      frameIndex: 0,
      frameLabel: { score: 0.12, taxon: { name: 'Noctua pronuba' } },
      hasVector: true,
    })
    expect(second.label).toBe('No classification')
    expect(second.hasVector).toBe(false)
    // A missing crop keeps the bounding box's proportions.
    expect(second.image).toEqual({
      height: 20,
      src: 'https://example.com/2.jpg',
      width: 10,
    })
  })

  test('each frame links to the full capture it was cropped from, when there is one', () => {
    const [first, second] = occurrence.firstFramesPage

    expect(first.captureUrl).toBe('https://example.com/capture-101.jpg')
    expect(second.captureUrl).toBeUndefined()
  })

  test('the track ends and label counts cover every frame, not just the first page', () => {
    expect(occurrence.lastFrame).toMatchObject({
      captureId: '140',
      frameIndex: 39,
      id: '40',
    })
    expect(
      occurrence.frameNames.map(({ frames, taxon }) => [taxon?.name, frames])
    ).toEqual([
      ['Noctua pronuba', 30],
      [undefined, 10],
    ])
  })
})
