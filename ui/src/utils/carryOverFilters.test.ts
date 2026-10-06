import { FILTERS_TO_OCCURRENCES } from 'pages/occurrences/occurrence-filters'
import { FILTERS_TO_TAXA } from 'pages/species/species-filters'
import { buildCarryOverFilters } from 'utils/buildCarryOverFilters'

describe('buildCarryOverFilters', () => {
  it('carries only active filters whose field is in the destination set', () => {
    const filters = [
      { field: 'deployment', value: '5' },
      { field: 'verified', value: 'false' },
      // active, but not part of the occurrence carry contract -> dropped
      { field: 'include_unobserved', value: 'true' },
      // part of the set, but inactive -> dropped
      { field: 'taxon', value: undefined },
    ]

    expect(buildCarryOverFilters(filters, FILTERS_TO_OCCURRENCES)).toEqual({
      deployment: '5',
      verified: 'false',
    })
  })

  it('returns an empty object when no active filter is in the set', () => {
    const filters = [{ field: 'page', value: '3' }]

    expect(buildCarryOverFilters(filters, FILTERS_TO_OCCURRENCES)).toEqual({})
  })
})

describe('carry-over contracts', () => {
  // Source-only state must never carry into a destination URL, regardless of destination.
  const SOURCE_ONLY = ['page', 'ordering']

  it.each([
    ['FILTERS_TO_OCCURRENCES', FILTERS_TO_OCCURRENCES],
    ['FILTERS_TO_TAXA', FILTERS_TO_TAXA],
  ])(
    '%s carries no pagination or sort state and has no duplicates',
    (_n, fields) => {
      expect(fields.filter((f) => SOURCE_ONLY.includes(f))).toEqual([])
      expect(new Set(fields).size).toBe(fields.length)
    }
  )

  it('keeps "show unobserved taxa" a taxa-only filter, never carried to occurrences', () => {
    expect(FILTERS_TO_TAXA).toContain('include_unobserved')
    expect(FILTERS_TO_OCCURRENCES).not.toContain('include_unobserved')
  })
})
