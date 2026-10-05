import { getOccurrenceHistoryQueryKey } from 'data-services/hooks/occurrences/useOccurrenceHistory'
import { API_ROUTES } from 'data-services/constants'
import { Algorithm } from './algorithm'
import { HumanIdentification, MachinePrediction } from './occurrence-details'
import {
  getFallbackTimelineItems,
  getJobSettings,
  getResultPrediction,
  getTimelineItems,
  ServerOccurrenceHistoryEntry,
} from './occurrence-history'
import { Taxon } from './taxa'
import { UserPermission } from 'utils/user/types'

const NOCTUA = { id: 3, name: 'Noctua pronuba', rank: 'SPECIES' }
const XESTIA = { id: 4, name: 'Xestia c-nigrum', rank: 'SPECIES' }

const base = {
  algorithm: null,
  job: null,
  score: null,
  taxon: null,
  timestamp: '2026-04-29T22:00:00',
  user: null,
}

const JOB = {
  config: { taxa_list_id: 2 },
  id: 30,
  name: 'Masking run',
  references: { taxa_list_id: { type: 'taxa_list', id: 2, name: 'Kept' } },
}

const identificationEntry = (id: number): ServerOccurrenceHistoryEntry => ({
  ...base,
  id,
  details: {
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
  taxon: typeof NOCTUA | null = XESTIA,
  supersededByResultId: number | null = null,
  job: typeof JOB | null = null
): ServerOccurrenceHistoryEntry => ({
  ...base,
  algorithm: { id: 7, key: 'classifier', name: 'Classifier' },
  id,
  job,
  details: {
    applied_to_id: null,
    detection_id: 1,
    superseded_by_result_id: supersededByResultId,
    terminal: true,
  },
  score: 0.8,
  taxon,
  type: 'prediction',
})

const classMasking: ServerOccurrenceHistoryEntry = {
  ...base,
  algorithm: { id: 12, key: 'mask', name: 'Masked classifier' },
  classifications: [
    {
      detection_id: 1,
      id: 20,
      replaced: { id: 6, score: 0.83, taxon: XESTIA },
      score: 0.7,
      taxon: NOCTUA,
      terminal: true,
    },
    {
      detection_id: 2,
      id: 21,
      replaced: null,
      score: 0.4,
      taxon: XESTIA,
      terminal: true,
    },
  ],
  data: {
    determination_after_id: 3,
    determination_before_id: 4,
    excluded_probability: 0.38,
    extra: {},
    new_winner_original_rank: 2,
  },
  data_references: {},
  determination_after: NOCTUA,
  determination_before: XESTIA,
  id: 5,
  is_current: true,
  job: JOB,
  kind: 'class_masking',
  score: 0.38,
  type: 'algorithm_result',
}

const ownIdentification: HumanIdentification = {
  comment: '',
  createdAt: '2026-04-29T22:00:00',
  id: '1',
  taxon: new Taxon({ ...NOCTUA, id: `${NOCTUA.id}`, cover_image_url: null }),
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
      entries: [classMasking, identificationEntry(2), predictionEntry(6)],
      identifications: [],
      predictions: [],
    })

    expect(items.map((item) => item.type)).toEqual([
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

  test('names the result that superseded a demoted prediction', () => {
    const items = getTimelineItems({
      entries: [
        classMasking,
        predictionEntry(6, XESTIA, 5),
        predictionEntry(8),
      ],
      identifications: [],
      predictions: [],
    })

    expect(items[1]).toMatchObject({ supersededBy: classMasking })
    expect(items[2]).not.toHaveProperty('supersededBy', expect.anything())
  })

  test('carries the job that wrote a prediction as a reference', () => {
    const items = getTimelineItems({
      entries: [predictionEntry(6, XESTIA, null, JOB), predictionEntry(8)],
      identifications: [],
      predictions: [],
    })

    expect(items[0]).toMatchObject({
      job: { type: 'job', id: 30, name: 'Masking run' },
    })
    expect(items[1]).not.toHaveProperty('job', expect.anything())
  })

  test('drops results of a kind it has no card for, and predictions without a taxon', () => {
    // A kind the server added before the UI has a card for it, e.g. tracking.
    const unknown = {
      ...classMasking,
      kind: 'tracking',
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

describe('cards built from the history', () => {
  test('are left out when a prediction names no algorithm or an identification no taxon', () => {
    expect(
      getTimelineItems({
        entries: [
          { ...predictionEntry(6), algorithm: null },
          { ...identificationEntry(2), taxon: null },
        ],
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
        ownPrediction('7', 12, NOCTUA, '2026-04-29T20:00:00'),
      ],
    })

    expect(items.map((item) => item.id)).toEqual([
      'prediction-6',
      'identification-1',
      'prediction-7',
    ])
  })

  test('breaks timestamp ties on id, newest first, as the server does', () => {
    const items = getFallbackTimelineItems({
      identifications: [ownIdentification],
      predictions: [ownPrediction('6', 7, NOCTUA, ownIdentification.createdAt)],
    })

    expect(items.map((item) => item.id)).toEqual([
      'prediction-6',
      'identification-1',
    ])
  })
})

describe('fallback predictions', () => {
  const tied = (id: string, terminal: boolean, createdAt: string) => ({
    ...ownPrediction(id, 7, NOCTUA, createdAt),
    terminal,
  })

  test('keep one per algorithm when detections tie for its top score', () => {
    const items = getFallbackTimelineItems({
      identifications: [],
      predictions: [
        tied('6', true, '2026-04-29T21:00:00'),
        tied('7', true, '2026-04-29T22:00:00'),
        ownPrediction('8', 12),
      ],
    })

    expect(items.map((item) => item.id)).toEqual([
      'prediction-7',
      'prediction-8',
    ])
  })

  test('prefer a terminal prediction over a later intermediate one', () => {
    const items = getFallbackTimelineItems({
      identifications: [],
      predictions: [
        tied('6', true, '2026-04-29T21:00:00'),
        tied('7', false, '2026-04-29T22:00:00'),
      ],
    })

    expect(items.map((item) => item.id)).toEqual(['prediction-6'])
  })
})

describe('getResultPrediction', () => {
  test('is the best classification the run created, marked applied when it is the determination', () => {
    expect(getResultPrediction(classMasking as never, '3')).toMatchObject({
      applied: true,
      count: 2,
      id: '20',
      score: 0.7,
      taxon: { id: '3', name: 'Noctua pronuba' },
    })
    expect(getResultPrediction(classMasking as never, '4')).toMatchObject({
      applied: false,
    })
  })

  test('is undefined for a run that created no classification', () => {
    expect(
      getResultPrediction(
        { ...classMasking, classifications: [] } as never,
        '3'
      )
    ).toBeUndefined()
  })
})

describe('getOccurrenceHistoryQueryKey', () => {
  test('sits under the occurrences key that mutations invalidate', () => {
    expect(getOccurrenceHistoryQueryKey('100')[0]).toBe(API_ROUTES.OCCURRENCES)
  })
})

describe('getJobSettings', () => {
  test('lists the settings a job ran with and the records they name, leaving out unset ones', () => {
    const deletedList = { type: 'taxa_list', id: 2, name: null }
    expect(
      getJobSettings({
        config: {
          occurrence_id: 4,
          reweight: true,
          size_threshold: 0.01,
          source_image_collection_id: null,
          taxa_list_id: 2,
        },
        id: 1,
        name: 'Size filter',
        references: {
          occurrence_id: { type: 'occurrence', id: 4, name: '#4' },
          taxa_list_id: deletedList,
        },
      })
    ).toEqual([
      {
        key: 'occurrence_id',
        value: 4,
        ref: { type: 'occurrence', id: 4, name: '#4' },
      },
      { key: 'reweight', value: true, ref: undefined },
      // A deleted list keeps its reference with no name, so the card shows its id as text.
      { key: 'taxa_list_id', value: 2, ref: deletedList },
    ])
  })

  test('is empty for a job without settings', () => {
    expect(
      getJobSettings({ config: null, id: 1, name: 'Pipeline', references: {} })
    ).toEqual([])
    expect(getJobSettings(null)).toEqual([])
  })
})
