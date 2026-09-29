import { getExportTypes } from './export'

// The kit's entry point pulls in stylesheets, which Jest does not load.
jest.mock('nova-ui-kit', () => ({
  CONSTANTS: jest.requireActual('nova-ui-kit/constants').CONSTANTS,
}))

describe('getExportTypes', () => {
  test('offers the tracks export only when tracking is on', () => {
    expect(getExportTypes({ trackingEnabled: false })).not.toContain(
      'tracks_csv'
    )
    expect(getExportTypes({ trackingEnabled: true })).toContain('tracks_csv')
  })

  test('always offers the occurrence exports', () => {
    expect(getExportTypes({ trackingEnabled: false })).toEqual([
      'occurrences_simple_csv',
      'occurrences_api_json',
    ])
  })
})
