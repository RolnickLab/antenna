import { AVAILABLE_FILTERS } from './useFilters'

// AVAILABLE_FILTERS is a pure factory function that takes a projectId and
// returns the full list of filter configurations. We test it without any
// React context because it does not depend on hooks.

describe('AVAILABLE_FILTERS', () => {
  const filters = AVAILABLE_FILTERS('test-project-1')

  describe('Device filter', () => {
    test('includes a filter with field deployment__device', () => {
      const deviceFilter = filters.find((f) => f.field === 'deployment__device')
      expect(deviceFilter).toBeDefined()
    })

    test('device filter has label "Device"', () => {
      const deviceFilter = filters.find((f) => f.field === 'deployment__device')
      expect(deviceFilter?.label).toBe('Device')
    })

    test('device filter has no tooltip', () => {
      const deviceFilter = filters.find((f) => f.field === 'deployment__device')
      expect(deviceFilter?.tooltip).toBeUndefined()
    })

    test('device filter has no validate function', () => {
      const deviceFilter = filters.find((f) => f.field === 'deployment__device')
      expect(deviceFilter?.validate).toBeUndefined()
    })
  })

  describe('Site filter', () => {
    test('includes a filter with field deployment__research_site', () => {
      const siteFilter = filters.find(
        (f) => f.field === 'deployment__research_site'
      )
      expect(siteFilter).toBeDefined()
    })

    test('site filter has label "Site"', () => {
      const siteFilter = filters.find(
        (f) => f.field === 'deployment__research_site'
      )
      expect(siteFilter?.label).toBe('Site')
    })

    test('site filter has no tooltip', () => {
      const siteFilter = filters.find(
        (f) => f.field === 'deployment__research_site'
      )
      expect(siteFilter?.tooltip).toBeUndefined()
    })

    test('site filter has no validate function', () => {
      const siteFilter = filters.find(
        (f) => f.field === 'deployment__research_site'
      )
      expect(siteFilter?.validate).toBeUndefined()
    })
  })

  describe('ordering', () => {
    test('device filter appears directly after deployment (station) filter', () => {
      const fieldNames = filters.map((f) => f.field)
      const deploymentIdx = fieldNames.indexOf('deployment')
      const deviceIdx = fieldNames.indexOf('deployment__device')
      expect(deploymentIdx).toBeGreaterThanOrEqual(0)
      expect(deviceIdx).toBe(deploymentIdx + 1)
    })

    test('site filter appears directly after device filter', () => {
      const fieldNames = filters.map((f) => f.field)
      const deviceIdx = fieldNames.indexOf('deployment__device')
      const siteIdx = fieldNames.indexOf('deployment__research_site')
      expect(siteIdx).toBe(deviceIdx + 1)
    })
  })

  describe('no duplicate fields', () => {
    test('each field name appears exactly once', () => {
      const fieldNames = filters.map((f) => f.field)
      const uniqueFields = new Set(fieldNames)
      // If there are duplicates the Set will be smaller
      expect(fieldNames.length).toBe(uniqueFields.size)
    })
  })
})