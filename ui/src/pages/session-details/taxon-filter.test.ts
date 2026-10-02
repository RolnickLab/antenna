import { CaptureDetection } from 'data-services/models/capture'
import { filterDetectionsByTaxon } from './taxon-filter'

const detection = (
  id: string,
  determinationTaxonIds: string[]
): CaptureDetection => ({
  bbox: [0, 0, 10, 10],
  determinationTaxonIds,
  id,
  label: id,
  occurrenceMeetsCriteria: true,
  score: 0.9,
  scoreLabel: '0.90',
})

// Lineages: species → genus → family. The unidentified detection has no occurrence.
const DETECTIONS = [
  detection('species-a', ['a', 'genus', 'family']),
  detection('species-b', ['b', 'genus', 'family']),
  detection('other-family', ['c', 'other-genus', 'other-family']),
  detection('unidentified', []),
]

describe('filterDetectionsByTaxon', () => {
  test('returns every detection when no taxon is selected', () => {
    expect(filterDetectionsByTaxon(DETECTIONS, undefined)).toBe(DETECTIONS)
  })

  test('keeps the detections determined as the taxon itself', () => {
    expect(filterDetectionsByTaxon(DETECTIONS, 'a').map((d) => d.id)).toEqual([
      'species-a',
    ])
  })

  test('keeps the detections determined as a descendant of the taxon', () => {
    expect(
      filterDetectionsByTaxon(DETECTIONS, 'genus').map((d) => d.id)
    ).toEqual(['species-a', 'species-b'])
  })

  test('drops detections without an occurrence and unrelated lineages', () => {
    expect(filterDetectionsByTaxon(DETECTIONS, 'missing')).toEqual([])
  })
})
