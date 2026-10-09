import {
  formatMetadata,
  parseMetadata,
  validateMetadata,
} from './fieldProcessors'

describe('formatMetadata', () => {
  test('shows an empty field when the record has no metadata', () => {
    const noMetadata = [undefined, null, {}]
    const results = noMetadata.map((testCase) => formatMetadata(testCase))
    expect(results).toEqual(['', '', ''])
  })

  test('indents the stored object so its keys are readable in the field', () => {
    expect(formatMetadata({ habitat: 'forest' })).toBe(
      '{\n  "habitat": "forest"\n}'
    )
  })
})

describe('parseMetadata', () => {
  test('reads an empty field as a record with no metadata', () => {
    const emptyFields = [undefined, '', '   ']
    const results = emptyFields.map((testCase) => parseMetadata(testCase))
    expect(results).toEqual([{}, {}, {}])
  })

  test('turns the typed text into the object the API stores', () => {
    expect(parseMetadata('{"habitat": "forest", "elevation_m": 320}')).toEqual({
      habitat: 'forest',
      elevation_m: 320,
    })
  })
})

describe('validateMetadata', () => {
  test('accepts an empty field, because metadata is optional', () => {
    const emptyFields = [undefined, '', '   ']
    const results = emptyFields.map((testCase) => validateMetadata(testCase))
    expect(results).toEqual([undefined, undefined, undefined])
  })

  test('accepts a JSON object', () => {
    expect(validateMetadata('{"habitat": "forest"}')).toBeUndefined()
    expect(validateMetadata('{}')).toBeUndefined()
  })

  test('reports text that is not valid JSON', () => {
    const malformed = ['{', '{habitat: forest}', '{"habitat": "forest",}']
    malformed.forEach((testCase) => {
      expect(validateMetadata(testCase)).toBe(
        'This is not valid JSON. Check for a missing quote, comma or bracket.'
      )
    })
  })

  test('reports valid JSON that is not a set of names and values', () => {
    // These all parse, so only the object check keeps them out of the API,
    // which stores metadata as an object and nothing else.
    const notObjects = ['[1, 2, 3]', '"forest"', '320', 'true', 'null']
    notObjects.forEach((testCase) => {
      expect(validateMetadata(testCase)).toBe(
        'Metadata must be a set of names and values wrapped in curly brackets, for example {"habitat": "forest"}.'
      )
    })
  })
})
