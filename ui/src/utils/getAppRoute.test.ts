import { getAppRoute } from './getAppRoute'

describe('getAppRoute', () => {
  describe('deployment__device filter', () => {
    test('includes deployment__device as a query param', () => {
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: { deployment__device: '42' },
      })
      expect(url).toBe('/projects/1/occurrences?deployment__device=42')
    })

    test('combines deployment__device with taxon filter', () => {
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: { deployment__device: '42', taxon: '7' },
      })
      const parsed = new URL(url, 'http://localhost')
      expect(parsed.searchParams.get('deployment__device')).toBe('42')
      expect(parsed.searchParams.get('taxon')).toBe('7')
    })
  })

  describe('deployment__research_site filter', () => {
    test('includes deployment__research_site as a query param', () => {
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: { deployment__research_site: '99' },
      })
      expect(url).toBe('/projects/1/occurrences?deployment__research_site=99')
    })

    test('combines deployment__research_site with taxon and verified filters', () => {
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: {
          deployment__research_site: '99',
          taxon: '7',
          verified: 'true',
        },
      })
      const parsed = new URL(url, 'http://localhost')
      expect(parsed.searchParams.get('deployment__research_site')).toBe('99')
      expect(parsed.searchParams.get('taxon')).toBe('7')
      expect(parsed.searchParams.get('verified')).toBe('true')
    })
  })

  describe('date_end and date_start filters', () => {
    test('includes date_end as a query param', () => {
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: { date_end: '2024-12-31' },
      })
      expect(url).toBe('/projects/1/occurrences?date_end=2024-12-31')
    })

    test('includes date_start as a query param', () => {
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: { date_start: '2024-01-01' },
      })
      expect(url).toBe('/projects/1/occurrences?date_start=2024-01-01')
    })

    test('includes both date_start and date_end together', () => {
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: { date_start: '2024-01-01', date_end: '2024-12-31' },
      })
      const parsed = new URL(url, 'http://localhost')
      expect(parsed.searchParams.get('date_start')).toBe('2024-01-01')
      expect(parsed.searchParams.get('date_end')).toBe('2024-12-31')
    })
  })

  describe('not_taxa_list_id filter', () => {
    test('includes not_taxa_list_id as a query param', () => {
      const url = getAppRoute({
        to: '/projects/1/taxa',
        filters: { not_taxa_list_id: '5' },
      })
      expect(url).toBe('/projects/1/taxa?not_taxa_list_id=5')
    })
  })

  describe('undefined filter values', () => {
    test('omits filter keys with undefined values', () => {
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: {
          deployment__device: undefined,
          deployment__research_site: undefined,
          taxon: '7',
        },
      })
      expect(url).toBe('/projects/1/occurrences?taxon=7')
    })

    test('returns base path with no query string when all filters are undefined', () => {
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: {
          deployment__device: undefined,
          deployment__research_site: undefined,
        },
      })
      expect(url).toBe('/projects/1/occurrences')
    })
  })

  describe('carryFilters spread pattern (device + site + taxon)', () => {
    test('carries deployment__device, deployment__research_site, and taxon together', () => {
      const carryFilters: Record<string, string> = {
        deployment__device: '3',
        deployment__research_site: '8',
      }
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: { ...carryFilters, taxon: '12' },
      })
      const parsed = new URL(url, 'http://localhost')
      expect(parsed.searchParams.get('deployment__device')).toBe('3')
      expect(parsed.searchParams.get('deployment__research_site')).toBe('8')
      expect(parsed.searchParams.get('taxon')).toBe('12')
    })

    test('carries deployment__device, deployment__research_site, taxon, and verified together', () => {
      const carryFilters: Record<string, string> = {
        deployment__device: '3',
        deployment__research_site: '8',
      }
      const url = getAppRoute({
        to: '/projects/1/occurrences',
        filters: { ...carryFilters, taxon: '12', verified: 'true' },
      })
      const parsed = new URL(url, 'http://localhost')
      expect(parsed.searchParams.get('deployment__device')).toBe('3')
      expect(parsed.searchParams.get('deployment__research_site')).toBe('8')
      expect(parsed.searchParams.get('taxon')).toBe('12')
      expect(parsed.searchParams.get('verified')).toBe('true')
    })
  })

  describe('base behaviour (regression)', () => {
    test('returns base path unchanged when no filters are provided', () => {
      const url = getAppRoute({ to: '/projects/1/occurrences' })
      expect(url).toBe('/projects/1/occurrences')
    })

    test('returns base path unchanged when filters is an empty object', () => {
      const url = getAppRoute({ to: '/projects/1/occurrences', filters: {} })
      expect(url).toBe('/projects/1/occurrences')
    })
  })
})