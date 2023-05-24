import { getCompactDatespanString } from './getCompactDatespanString'

describe('getCompactDatespanString', () => {
  const locale = 'en-GB'

  test('returns a compact timespan string', () => {
    const date1 = new Date('2022-06-20T20:02:00')
    const date2 = new Date('2023-06-21T05:23:00')
    const timespanString = getCompactDatespanString({
      date1,
      date2,
      locale,
    })

    expect(timespanString).toBe('Jun 20, 2022 - Jun 21, 2023')
  })

  test('combines year if the same', () => {
    const date1 = new Date('2022-06-20T20:02:00')
    const date2 = new Date('2022-07-21T05:23:00')
    const timespanString = getCompactDatespanString({
      date1,
      date2,
      locale,
    })

    expect(timespanString).toBe('Jun 20 - Jul 21, 2022')
  })

  test('combines month and year if the same', () => {
    const date1 = new Date('2022-06-20T20:02:00')
    const date2 = new Date('2022-06-21T05:23:00')
    const timespanString = getCompactDatespanString({
      date1,
      date2,
      locale,
    })

    expect(timespanString).toBe('Jun 20-21, 2022')
  })

  test('combines day, month and year if the same', () => {
    const date1 = new Date('2022-06-20T05:23:00')
    const date2 = new Date('2022-06-20T20:02:00')
    const timespanString = getCompactDatespanString({
      date1,
      date2,
      locale,
    })

    expect(timespanString).toBe('Jun 20, 2022')
  })
})
