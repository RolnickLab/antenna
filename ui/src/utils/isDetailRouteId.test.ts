import { isDetailRouteId } from 'utils/isDetailRouteId'

describe('isDetailRouteId', () => {
  it('accepts a positive integer string', () => {
    expect(isDetailRouteId('12')).toBe(true)
  })

  it.each([
    'lists', // a sibling collection path segment
    'foo', // non-numeric text
    '', // an empty string
    undefined, // a missing id
    '1.5', // a decimal
    '-1', // a negative number
    ' 1', // leading whitespace
    '0', // zero, since primary keys start at 1
  ])('rejects %s', (id: string | undefined) => {
    expect(isDetailRouteId(id)).toBe(false)
  })
})
