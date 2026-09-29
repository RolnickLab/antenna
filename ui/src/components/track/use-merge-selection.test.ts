import { act, renderHook } from '@testing-library/react'
import { keepOfferedIds, useMergeSelection } from './use-merge-selection'

// The adjacent-capture scope offers two rows; a wider scope also offers a third.
const ADJACENT = [{ id: 'o1' }, { id: 'o2' }]
const WIDER = [{ id: 'o1' }, { id: 'o2' }, { id: 'o3' }]
const NARROWER = [{ id: 'o1' }]

const renderSelection = () =>
  renderHook(
    (props: { candidates: { id: string }[]; isLoading: boolean }) =>
      useMergeSelection(props),
    { initialProps: { candidates: ADJACENT, isLoading: false } }
  )

describe('keepOfferedIds', () => {
  test('drops a tick the candidates no longer offer', () => {
    expect(keepOfferedIds(['o1', 'o2'], NARROWER)).toEqual(['o1'])
  })

  test('returns the same ids when every tick still stands', () => {
    const selectedIds = ['o1', 'o2']

    expect(keepOfferedIds(selectedIds, WIDER)).toBe(selectedIds)
  })
})

describe('useMergeSelection', () => {
  test('a wider list of candidates keeps every tick', () => {
    const { rerender, result } = renderSelection()
    act(() => {
      result.current.toggle('o1')
      result.current.toggle('o2')
    })

    rerender({ candidates: WIDER, isLoading: false })

    expect(result.current.selectedIds).toEqual(['o1', 'o2'])
  })

  test('candidates still being fetched keep every tick', () => {
    const { rerender, result } = renderSelection()
    act(() => {
      result.current.toggle('o1')
      result.current.toggle('o2')
    })

    rerender({ candidates: [], isLoading: true })

    expect(result.current.selectedIds).toEqual(['o1', 'o2'])
  })

  test('a narrower list drops the ticks it no longer offers', () => {
    const { rerender, result } = renderSelection()
    act(() => {
      result.current.toggle('o1')
      result.current.toggle('o2')
    })

    rerender({ candidates: NARROWER, isLoading: false })

    expect(result.current.selectedIds).toEqual(['o1'])
  })

  test('clearing empties the selection', () => {
    const { result } = renderSelection()
    act(() => {
      result.current.toggle('o1')
    })
    act(() => {
      result.current.clear()
    })

    expect(result.current.selectedIds).toEqual([])
  })
})
