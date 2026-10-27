import { AVAILABLE_FILTERS } from 'utils/useFilters'

// ts-jest cannot compile constants.ts (import.meta). The filters only use it for tooltip links.
jest.mock('utils/constants', () => ({
  APP_ROUTES: new Proxy({}, { get: () => () => '' }),
}))

const validateDateStart = (dateStart: string, dateEnd: string) => {
  const config = AVAILABLE_FILTERS('1').find(
    (filter) => filter.field === 'date_start'
  )

  return config?.validate?.(dateStart, [{ field: 'date_end', value: dateEnd }])
}

describe('date_start validation', () => {
  // A filter with an error is left out of the request, so rejecting equal dates
  // would silently turn a single-day range into "everything up to the end date".
  it('accepts a single-day range', () => {
    expect(validateDateStart('2024-06-19', '2024-06-19')).toBeUndefined()
  })

  it('rejects a start date after the end date', () => {
    expect(validateDateStart('2024-06-20', '2024-06-19')).toBeDefined()
  })
})
