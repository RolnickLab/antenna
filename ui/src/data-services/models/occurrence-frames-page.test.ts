import { OccurrenceFrame } from './occurrence-details'
import {
  getFramePageQuery,
  getFrameRange,
  getLinkedFramePage,
  isFirstFramePage,
} from './occurrence-frames-page'

const frame = (frameIndex: number) =>
  ({ frameIndex, id: `${frameIndex + 1}` } as OccurrenceFrame)

describe('frame pages', () => {
  test('a neighbouring page is read off the link, and a link without an offset is the first page', () => {
    expect(
      getLinkedFramePage(
        'http://localhost/api/v2/occurrences/1/detections/?limit=20&offset=40'
      )
    ).toEqual({ offset: 40 })
    expect(
      getLinkedFramePage(
        'http://localhost/api/v2/occurrences/1/detections/?limit=20'
      )
    ).toEqual({ offset: 0 })
    expect(getLinkedFramePage(null)).toBeUndefined()
  })

  test('only offset 0 is the page the detail already carries', () => {
    expect(isFirstFramePage({ offset: 0 })).toBe(true)
    expect(isFirstFramePage({ offset: 20 })).toBe(false)
    expect(isFirstFramePage({ around: '7' })).toBe(false)
  })

  test('a page is requested by offset or by the detection it must hold', () => {
    expect(getFramePageQuery({ offset: 20 })).toBe('offset=20')
    expect(getFramePageQuery({ around: '7' })).toBe('around=7')
  })

  test('the range counts frames from 1 across the whole track', () => {
    expect(getFrameRange([frame(20), frame(21), frame(39)])).toEqual({
      end: 40,
      start: 21,
    })
    expect(getFrameRange([])).toBeUndefined()
  })
})
