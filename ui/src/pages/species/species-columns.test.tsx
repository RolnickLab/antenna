import { render, screen } from '@testing-library/react'
import { Species } from 'data-services/models/species'
import React from 'react'
import { MemoryRouter } from 'react-router-dom'
import { columns } from './species-columns'

// Mock heavy UI dependencies so the column renderCell functions can be
// rendered in isolation without a full app setup.

jest.mock('nova-ui-kit', () => ({
  BasicTableCell: ({ children, value }: { children?: React.ReactNode; value?: unknown }) =>
    children ? <span>{children}</span> : <span>{String(value ?? '')}</span>,
  CellTheme: { Bubble: 'Bubble' },
  DateTableCell: () => null,
  ImageCellTheme: { Light: 'Light' },
  ImageTableCell: () => null,
  TableColumn: {},
  TextAlign: { Right: 'right' },
}))

jest.mock('components/determination-score', () => ({
  DeterminationScore: () => null,
}))

jest.mock('components/taxon-details/taxon-details', () => ({
  TaxonDetails: () => null,
}))

jest.mock('components/taxon-tags/tag', () => ({
  Tag: () => null,
}))

jest.mock('utils/language', () => ({
  STRING: {},
  translate: (key: unknown) => String(key),
}))

// Helper: build a minimal Species instance.
function makeSpecies(id: string): Species {
  return new Species({
    id,
    name: 'Vanessa cardui',
    rank: 'SPECIES',
    cover_image_url: null,
    occurrences_count: 5,
    verified_count: 2,
  })
}

// Helper: render a single cell wrapped in MemoryRouter and return its container.
function renderCell(
  column: ReturnType<typeof columns>[number],
  item: Species
) {
  const { container } = render(
    <MemoryRouter>{column.renderCell(item)}</MemoryRouter>
  )
  return container
}

describe('species-columns carryFilters', () => {
  const projectId = 'proj-1'
  const item = makeSpecies('taxon-7')

  describe('occurrences column', () => {
    test('occurrence link includes only taxon when carryFilters is empty', () => {
      const cols = columns({ projectId, carryFilters: {} })
      const col = cols.find((c) => c.id === 'occurrences')!
      const container = renderCell(col, item)
      const anchor = container.querySelector('a')
      expect(anchor).not.toBeNull()
      const url = new URL(anchor!.getAttribute('href')!, 'http://localhost')
      expect(url.searchParams.get('taxon')).toBe('taxon-7')
      expect(url.searchParams.get('deployment__device')).toBeNull()
      expect(url.searchParams.get('deployment__research_site')).toBeNull()
    })

    test('occurrence link includes deployment__device from carryFilters', () => {
      const cols = columns({
        projectId,
        carryFilters: { deployment__device: '42' },
      })
      const col = cols.find((c) => c.id === 'occurrences')!
      const container = renderCell(col, item)
      const anchor = container.querySelector('a')
      const url = new URL(anchor!.getAttribute('href')!, 'http://localhost')
      expect(url.searchParams.get('deployment__device')).toBe('42')
      expect(url.searchParams.get('taxon')).toBe('taxon-7')
    })

    test('occurrence link includes deployment__research_site from carryFilters', () => {
      const cols = columns({
        projectId,
        carryFilters: { deployment__research_site: '99' },
      })
      const col = cols.find((c) => c.id === 'occurrences')!
      const container = renderCell(col, item)
      const anchor = container.querySelector('a')
      const url = new URL(anchor!.getAttribute('href')!, 'http://localhost')
      expect(url.searchParams.get('deployment__research_site')).toBe('99')
      expect(url.searchParams.get('taxon')).toBe('taxon-7')
    })

    test('occurrence link includes both device and site from carryFilters', () => {
      const cols = columns({
        projectId,
        carryFilters: { deployment__device: '3', deployment__research_site: '8' },
      })
      const col = cols.find((c) => c.id === 'occurrences')!
      const container = renderCell(col, item)
      const anchor = container.querySelector('a')
      const url = new URL(anchor!.getAttribute('href')!, 'http://localhost')
      expect(url.searchParams.get('deployment__device')).toBe('3')
      expect(url.searchParams.get('deployment__research_site')).toBe('8')
      expect(url.searchParams.get('taxon')).toBe('taxon-7')
    })

    test('taxon in carryFilters is overridden by the item taxon id', () => {
      // If carryFilters happened to contain a stale taxon key, the item.id wins.
      const cols = columns({
        projectId,
        carryFilters: { deployment__device: '3', taxon: 'old-taxon' } as any,
      })
      const col = cols.find((c) => c.id === 'occurrences')!
      const container = renderCell(col, item)
      const anchor = container.querySelector('a')
      const url = new URL(anchor!.getAttribute('href')!, 'http://localhost')
      expect(url.searchParams.get('taxon')).toBe('taxon-7')
    })
  })

  describe('verified column', () => {
    test('verified link includes verified=true and taxon', () => {
      const cols = columns({ projectId, carryFilters: {} })
      const col = cols.find((c) => c.id === 'verified')!
      const container = renderCell(col, item)
      const anchor = container.querySelector('a')
      const url = new URL(anchor!.getAttribute('href')!, 'http://localhost')
      expect(url.searchParams.get('taxon')).toBe('taxon-7')
      expect(url.searchParams.get('verified')).toBe('true')
    })

    test('verified link includes deployment__device from carryFilters', () => {
      const cols = columns({
        projectId,
        carryFilters: { deployment__device: '42' },
      })
      const col = cols.find((c) => c.id === 'verified')!
      const container = renderCell(col, item)
      const anchor = container.querySelector('a')
      const url = new URL(anchor!.getAttribute('href')!, 'http://localhost')
      expect(url.searchParams.get('deployment__device')).toBe('42')
      expect(url.searchParams.get('taxon')).toBe('taxon-7')
      expect(url.searchParams.get('verified')).toBe('true')
    })

    test('verified link includes deployment__research_site from carryFilters', () => {
      const cols = columns({
        projectId,
        carryFilters: { deployment__research_site: '99' },
      })
      const col = cols.find((c) => c.id === 'verified')!
      const container = renderCell(col, item)
      const anchor = container.querySelector('a')
      const url = new URL(anchor!.getAttribute('href')!, 'http://localhost')
      expect(url.searchParams.get('deployment__research_site')).toBe('99')
      expect(url.searchParams.get('taxon')).toBe('taxon-7')
      expect(url.searchParams.get('verified')).toBe('true')
    })

    test('verified link includes both device and site from carryFilters', () => {
      const cols = columns({
        projectId,
        carryFilters: { deployment__device: '3', deployment__research_site: '8' },
      })
      const col = cols.find((c) => c.id === 'verified')!
      const container = renderCell(col, item)
      const anchor = container.querySelector('a')
      const url = new URL(anchor!.getAttribute('href')!, 'http://localhost')
      expect(url.searchParams.get('deployment__device')).toBe('3')
      expect(url.searchParams.get('deployment__research_site')).toBe('8')
      expect(url.searchParams.get('taxon')).toBe('taxon-7')
      expect(url.searchParams.get('verified')).toBe('true')
    })
  })

  describe('default carryFilters', () => {
    test('columns() works without carryFilters parameter (defaults to {})', () => {
      // No carryFilters argument – should not throw and links should work.
      const cols = columns({ projectId })
      const col = cols.find((c) => c.id === 'occurrences')!
      const container = renderCell(col, item)
      const anchor = container.querySelector('a')
      const url = new URL(anchor!.getAttribute('href')!, 'http://localhost')
      expect(url.searchParams.get('taxon')).toBe('taxon-7')
      expect(url.searchParams.get('deployment__device')).toBeNull()
    })
  })
})