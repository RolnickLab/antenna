import { Occurrence, ServerOccurrence } from './occurrence'

const serverOccurrence = (
  overrides: Record<string, unknown> = {}
): ServerOccurrence => ({
  id: 12,
  created_at: '2026-09-09T02:00:00',
  detection_images: ['https://example.com/crop.jpg'],
  detections_count: 1,
  determination: { id: 3, name: 'Noctua pronuba' },
  determination_details: {
    identification: null,
    prediction: { id: 5 },
    score: 0.91,
    taxon: {
      id: 3,
      name: 'Noctua pronuba',
      rank: 'SPECIES',
      cover_image_url: null,
    },
  },
  first_appearance_timestamp: '2026-09-09T02:00:00',
  identifications: [],
  track_stats: null,
  user_permissions: [],
  ...overrides,
})

describe('occurrence conversion', () => {
  test('names a determined occurrence after its taxon', () => {
    const occurrence = new Occurrence(serverOccurrence())

    expect(occurrence.determinationTaxon?.id).toBe('3')
    expect(occurrence.determinationScore).toBe(0.91)
    expect(occurrence.displayName).toBe('Noctua pronuba #12')
  })

  test('an occurrence nothing has identified still converts', () => {
    const occurrence = new Occurrence(
      serverOccurrence({
        determination: null,
        determination_details: {
          identification: null,
          prediction: null,
          score: null,
          taxon: null,
        },
      })
    )

    expect(occurrence.determinationTaxon).toBeUndefined()
    expect(occurrence.determinationId).toBeUndefined()
    expect(occurrence.determinationScore).toBeUndefined()
    expect(occurrence.determinationVerified).toBe(false)
    expect(occurrence.displayName).toBe('Unidentified #12')
  })

  test('an occurrence without determination details still converts', () => {
    const occurrence = new Occurrence(
      serverOccurrence({ determination: null, determination_details: null })
    )

    expect(occurrence.determinationTaxon).toBeUndefined()
    expect(occurrence.displayName).toBe('Unidentified #12')
  })
})
