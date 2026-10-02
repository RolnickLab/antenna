import { UserPermission } from 'utils/user/types'
import { getTrackEditRights } from './track-edit-rights'

describe('getTrackEditRights', () => {
  test('grants nothing without occurrence rights, as for an anonymous visitor', () => {
    expect(getTrackEditRights([])).toEqual({
      canRestructure: false,
      canVerify: false,
    })
    expect(getTrackEditRights(undefined)).toEqual({
      canRestructure: false,
      canVerify: false,
    })
  })

  test('lets the update right confirm a grouping but not restructure it', () => {
    expect(getTrackEditRights([UserPermission.Update])).toEqual({
      canRestructure: false,
      canVerify: true,
    })
  })

  test('lets the delete right restructure and confirm', () => {
    expect(getTrackEditRights([UserPermission.Delete])).toEqual({
      canRestructure: true,
      canVerify: true,
    })
  })
})
