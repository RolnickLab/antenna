import { getUserLabel } from './getUserLabel'

describe('getUserLabel', () => {
  test('names the current user "You" when they have no display name', () => {
    expect(getUserLabel({ id: 4, name: '' }, { id: '4', name: '' })).toBe('You')
    expect(
      getUserLabel(
        { id: 4, name: 'Unnamed user' },
        { id: '4', name: undefined }
      )
    ).toBe('You')
  })

  test('uses the display name of a user who has one, including the current user', () => {
    expect(getUserLabel({ id: 4, name: 'Ada' }, { id: '4', name: 'Ada' })).toBe(
      'Ada'
    )
    expect(getUserLabel({ id: 5, name: 'Ada' }, { id: '4' })).toBe('Ada')
  })

  test('labels another user without a display name as unnamed, not anonymous', () => {
    expect(getUserLabel({ id: 5, name: '' }, { id: '4' })).toBe('Unnamed user')
    expect(getUserLabel({ id: 5, name: null })).toBe('Unnamed user')
  })

  test('keeps "Anonymous user" for actions with no user', () => {
    expect(getUserLabel(undefined, { id: '4' })).toBe('Anonymous user')
    expect(getUserLabel(null)).toBe('Anonymous user')
  })
})
