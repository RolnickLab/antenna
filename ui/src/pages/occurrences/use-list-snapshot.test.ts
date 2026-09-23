import { renderHook } from '@testing-library/react'
import { useListSnapshot } from './use-list-snapshot'

const renderSnapshot = (items: { id: string }[] | undefined, listKey = 'a') =>
  renderHook(
    (props: { items?: { id: string }[]; listKey: string }) =>
      useListSnapshot(props.items, props.listKey),
    { initialProps: { items, listKey } }
  )

const ids = (items?: { id: string }[]) => items?.map(({ id }) => id)

describe('useListSnapshot', () => {
  test('keeps the first order when a refetch reorders the same list', () => {
    const { result, rerender } = renderSnapshot([
      { id: '1' },
      { id: '2' },
      { id: '3' },
    ])

    rerender({ items: [{ id: '2' }, { id: '1' }, { id: '3' }], listKey: 'a' })

    expect(ids(result.current)).toEqual(['1', '2', '3'])
  })

  test('takes a new order when the page, filters or sort change', () => {
    const { result, rerender } = renderSnapshot([{ id: '1' }, { id: '2' }])

    rerender({ items: undefined, listKey: 'b' })
    expect(result.current).toBeUndefined()

    rerender({ items: [{ id: '5' }, { id: '4' }], listKey: 'b' })
    expect(ids(result.current)).toEqual(['5', '4'])
  })

  test('waits for the list to load before taking the order', () => {
    const { result, rerender } = renderSnapshot(undefined)

    rerender({ items: [{ id: '1' }, { id: '2' }], listKey: 'a' })

    expect(ids(result.current)).toEqual(['1', '2'])
  })
})
