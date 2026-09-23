import { getAdjacentIds } from './adjacent-occurrences'

const items = [{ id: '1' }, { id: '2' }, { id: '3' }]

describe('getAdjacentIds', () => {
  test('returns both neighbours in the middle of the list', () => {
    expect(getAdjacentIds(items, '2')).toEqual({ prevId: '1', nextId: '3' })
  })

  test('has no next id on the last item, so confirming there closes the dialog', () => {
    expect(getAdjacentIds(items, '3')).toEqual({
      prevId: '2',
      nextId: undefined,
    })
  })

  test('returns nothing when the current item is not in the list', () => {
    expect(getAdjacentIds(items, '9')).toEqual({})
    expect(getAdjacentIds(undefined, '1')).toEqual({})
  })
})
