import { isEmpty } from './isEmpty'

describe('isEmpty', () => {
  test('returns true if value is empty string, null, or undefined', () => {
    const emptyTestCases = ['', '    ', null, undefined]
    const results = emptyTestCases.map((testCase) => isEmpty(testCase))
    expect(results).not.toContain(false)
  })

  test('returns false if value is not empty string, null, or undefined', () => {
    const notEmptyTestCases = ['cat', 1, [], {}, false, 0, -1, NaN]
    const results = notEmptyTestCases.map((testCase) => isEmpty(testCase))
    expect(results).not.toContain(true)
  })
})
