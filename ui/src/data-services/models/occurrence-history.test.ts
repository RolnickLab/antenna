import { getOccurrenceHistoryQueryKey } from 'data-services/hooks/occurrences/useOccurrenceHistory'
import { API_ROUTES } from 'data-services/constants'
import { Algorithm } from './algorithm'
import { HumanIdentification, MachinePrediction } from './occurrence-details'
import {
  getFallbackTimelineItems,
  getFoldedPrediction,
  getTimelineItems,
  isEditedSinceComplete,
  ServerOccurrenceHistoryEntry,
  TrackCompleteReviewEntry,
} from './occurrence-history'
import { Taxon } from './taxa'
import { UserPermission } from 'utils/user/types'

const NOCTUA = { id: 3, name: 'Noctua pronuba', rank: 'SPECIES' }
const XESTIA = { id: 4, name: 'Xestia c-nigrum', rank: 'SPECIES' }

const base = {
  algorithm: null,
  job: null,
  score: null,
  subtype: null,
  taxon: null,
  taxon_before: null,
  timestamp: '2026-04-29T22:00:00',
  user: null,
}

const identificationEntry = (id: number): ServerOccurrenceHistoryEntry => ({
  ...base,
  id,
  payload: {
    agreed_with_identification_id: null,
    agreed_with_prediction_id: null,
    comment: 'Looks right',
    withdrawn: false,
  },
  taxon: NOCTUA,
  type: 'identification',
  user: { id: 9, image: null, name: '' },
})

const predictionEntry = (
  id: number,
  taxon: typeof NOCTUA | null = XESTIA
): ServerOccurrenceHistoryEntry => ({
  ...base,
  algorithm: { id: 7, key: 'classifier', name: 'Classifier' },
  id,
  payload: { applied_to_id: null, detection_id: 1, terminal: true },
  score: 0.8,
  taxon,
  type: 'prediction',
})

const review = (
  id: number,
  detectionIds: number[],
  occurrenceId: number | null = 100
): TrackCompleteReviewEntry => ({
  ...base,
  id,
  payload: {
    detection_ids: detectionIds,
    detections_added: [],
    detections_removed: [],
    first_timestamp: null,
    frames_count: detectionIds.length,
    last_timestamp: null,
    occurrence_id: occurrenceId,
  },
  subtype: 'track_complete',
  type: 'review',
})

const classMasking: ServerOccurrenceHistoryEntry = {
  ...base,
  algorithm: { id: 12, key: 'mask', name: 'Masked classifier' },
  id: 5,
  payload: {
    detection_ids: [1],
    source_algorithm_id: 7,
    taxa_list_id: 2,
    taxon_after_id: 3,
    taxon_before_id: 4,
  },
  subtype: 'class_masking',
  taxon: NOCTUA,
  taxon_before: XESTIA,
  type: 'algorithm_result',
}

const ownIdentification: HumanIdentification = {
  comment: '',
  createdAt: '2026-04-29T22:00:00',
  id: '1',
  user: { name: 'Someone' },
  userPermissions: [UserPermission.Delete],
}

const ownPrediction = (
  id: string,
  algorithmId: number,
  taxon = NOCTUA,
  createdAt = '2026-04-29T21:00:00'
): MachinePrediction => ({
  algorithm: new Algorithm({ id: algorithmId }),
  createdAt,
  id,
  score: 0.9,
  taxon: new Taxon({ ...taxon, id: `${taxon.id}`, cover_image_url: null }),
  terminal: true,
  userPermissions: [UserPermission.Update],
})

describe('getTimelineItems', () => {
  test('maps each entry type to its card, keeping the server order', () => {
    const items = getTimelineItems({
      entries: [
        review(8, [1]),
        classMasking,
        identificationEntry(2),
        predictionEntry(6),
      ],
      identifications: [],
      predictions: [],
    })

    expect(items.map((item) => item.type)).toEqual([
      'review',
      'algorithm_result',
      'identification',
      'prediction',
    ])
  })

  test("reuses the occurrence's own records, which carry the viewer's permissions", () => {
    const prediction = ownPrediction('6', 7)
    const items = getTimelineItems({
      entries: [identificationEntry(1), predictionEntry(6)],
      identifications: [ownIdentification],
      predictions: [prediction],
    })

    expect(items[0]).toMatchObject({ identification: ownIdentification })
    expect(items[1]).toMatchObject({ prediction })
  })

  test('builds a read-only card when the occurrence lacks the record', () => {
    const [item] = getTimelineItems({
      determinationTaxonId: '3',
      entries: [identificationEntry(2)],
      identifications: [],
      predictions: [],
    })

    expect(item.type === 'identification' && item.identification).toMatchObject(
      {
        applied: true,
        comment: 'Looks right',
        user: { id: '9', name: 'Anonymous user' },
        userPermissions: [],
      }
    )
  })

  test('drops unknown subtypes and predictions without a taxon', () => {
    const unknown = {
      ...classMasking,
      subtype: 'something_new',
    } as unknown as ServerOccurrenceHistoryEntry

    expect(
      getTimelineItems({
        entries: [unknown, predictionEntry(6, null)],
        identifications: [],
        predictions: [],
      })
    ).toEqual([])
  })
})

describe('getFallbackTimelineItems', () => {
  test('merges identifications and predictions newest first', () => {
    const items = getFallbackTimelineItems({
      identifications: [ownIdentification],
      predictions: [
        ownPrediction('6', 7, NOCTUA, '2026-04-29T23:00:00'),
        ownPrediction('7', 7, NOCTUA, '2026-04-29T20:00:00'),
      ],
    })

    expect(items.map((item) => item.id)).toEqual([
      'prediction-6',
      'identification-1',
      'prediction-7',
    ])
  })
})

describe('getFoldedPrediction', () => {
  test('finds the prediction behind an algorithm result by its algorithm', () => {
    const folded = ownPrediction('6', 12)

    expect(
      getFoldedPrediction(classMasking as never, [
        ownPrediction('5', 7),
        folded,
      ])
    ).toBe(folded)
  })

  test('finds it when the determination differs from the predicted taxon', () => {
    const folded = ownPrediction('6', 12, XESTIA)

    expect(
      getFoldedPrediction(classMasking as never, [
        ownPrediction('5', 7),
        folded,
      ])
    ).toBe(folded)
  })
})

describe('isEditedSinceComplete', () => {
  test('false without a review', () => {
    expect(
      isEditedSinceComplete({
        detectionIds: ['1'],
        entries: [identificationEntry(1)],
        occurrenceId: '100',
      })
    ).toBe(false)
  })

  test('false when the detections match the latest review in any order', () => {
    expect(
      isEditedSinceComplete({
        detectionIds: ['2', '1'],
        entries: [review(9, [1, 2]), review(8, [1])],
        occurrenceId: '100',
      })
    ).toBe(false)
  })

  test('true when a detection was added or removed since the latest review', () => {
    const entries = [review(9, [1, 2])]

    expect(
      isEditedSinceComplete({
        detectionIds: ['1', '2', '3'],
        entries,
        occurrenceId: '100',
      })
    ).toBe(true)
    expect(
      isEditedSinceComplete({
        detectionIds: ['1'],
        entries,
        occurrenceId: '100',
      })
    ).toBe(true)
  })

  test('ignores reviews a merge brought in from another occurrence', () => {
    expect(
      isEditedSinceComplete({
        detectionIds: ['1', '2', '5'],
        entries: [review(9, [5], 200), review(8, [1, 2, 5])],
        occurrenceId: '100',
      })
    ).toBe(false)
  })
})

describe('getOccurrenceHistoryQueryKey', () => {
  test('sits under the occurrences key that mutations invalidate', () => {
    expect(getOccurrenceHistoryQueryKey('100')[0]).toBe(API_ROUTES.OCCURRENCES)
  })
})
