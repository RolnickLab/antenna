import { showSessionTimeline } from './utils'

const at = (minute: number, second = 0) =>
  new Date(2026, 0, 1, 22, minute, second)

describe('session timeline visibility', () => {
  const startDate = at(0)

  test('a session spanning less than a minute has no timeline', () => {
    expect(showSessionTimeline({ startDate, endDate: at(0, 59) })).toBe(false)
  })

  test('a session spanning a full minute keeps its timeline', () => {
    expect(showSessionTimeline({ startDate, endDate: at(1) })).toBe(true)
  })

  test('an unknown span keeps the timeline rather than hiding it', () => {
    expect(showSessionTimeline({ startDate, endDate: undefined })).toBe(true)
    expect(showSessionTimeline({ startDate, endDate: new Date(NaN) })).toBe(
      true
    )
  })
})
