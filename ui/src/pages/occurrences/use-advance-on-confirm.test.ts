import { renderHook } from '@testing-library/react'
import { useAdvanceOnConfirm } from './use-advance-on-confirm'

const items = [{ id: '1' }, { id: '2' }]

const renderAdvance = (currentId: string) => {
  const close = jest.fn()
  const goTo = jest.fn()
  const hook = renderHook(
    (props: { currentId: string }) =>
      useAdvanceOnConfirm({ close, currentId: props.currentId, goTo, items }),
    { initialProps: { currentId } }
  )

  return { close, goTo, ...hook }
}

describe('useAdvanceOnConfirm', () => {
  test('moves to the next item after a confirm', () => {
    const { close, goTo, result } = renderAdvance('1')

    result.current('1')

    expect(goTo).toHaveBeenCalledWith('2')
    expect(close).not.toHaveBeenCalled()
  })

  test('closes after a confirm on the last item', () => {
    const { close, goTo, result } = renderAdvance('2')

    result.current('2')

    expect(close).toHaveBeenCalled()
    expect(goTo).not.toHaveBeenCalled()
  })

  test('stays on a confirmed item that is not in the list, as from a deep link', () => {
    const { close, goTo, result } = renderAdvance('9')

    result.current('9')

    expect(close).not.toHaveBeenCalled()
    expect(goTo).not.toHaveBeenCalled()
  })

  test('ignores a confirm that finishes after the user moved to another item', () => {
    const { close, goTo, rerender, result } = renderAdvance('1')

    rerender({ currentId: '2' })
    result.current('1')

    expect(goTo).not.toHaveBeenCalled()
    expect(close).not.toHaveBeenCalled()
  })

  test('ignores a confirm that finishes after the dialog closed', () => {
    const { close, goTo, result, unmount } = renderAdvance('1')
    const onConfirmed = result.current

    unmount()
    onConfirmed('1')

    expect(goTo).not.toHaveBeenCalled()
    expect(close).not.toHaveBeenCalled()
  })
})
