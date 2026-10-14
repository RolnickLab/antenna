import { getUserLabel } from './getUserLabel'

describe('getUserLabel', () => {
  test('uses the display name of a user who has one', () => {
    expect(getUserLabel({ name: 'Ada' })).toBe('Ada')
  })

  test('reads "Anonymous user" for a user without a display name, as the identification cards do', () => {
    expect(getUserLabel({ name: '' })).toBe('Anonymous user')
    expect(getUserLabel({ name: null })).toBe('Anonymous user')
  })

  test('reads "Anonymous user" for an action with no user', () => {
    expect(getUserLabel(undefined)).toBe('Anonymous user')
    expect(getUserLabel(null)).toBe('Anonymous user')
  })
})
