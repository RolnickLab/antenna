import { UserPermission } from 'utils/user/types'
import { getExtendOccurrenceId } from './extend-access'

const track = {
  id: '10',
  sessionId: '5',
  userPermissions: [UserPermission.Update, UserPermission.Delete],
}

const opens = {
  enabled: true,
  requestedOccurrenceId: '10',
  sessionId: '5',
  track,
}

describe('getExtendOccurrenceId', () => {
  test('opens on an editable occurrence from this session', () => {
    expect(getExtendOccurrenceId(opens)).toBe('10')
  })

  test('stays closed while tracking is off or the occurrence is loading', () => {
    expect(getExtendOccurrenceId({ ...opens, enabled: false })).toBeUndefined()
    expect(
      getExtendOccurrenceId({ ...opens, track: undefined })
    ).toBeUndefined()
  })

  test('ignores an occurrence the viewer may not restructure', () => {
    expect(
      getExtendOccurrenceId({
        ...opens,
        track: { ...track, userPermissions: [UserPermission.Update] },
      })
    ).toBeUndefined()
    expect(
      getExtendOccurrenceId({
        ...opens,
        track: { ...track, userPermissions: [] },
      })
    ).toBeUndefined()
  })

  test('ignores an occurrence from another session', () => {
    expect(
      getExtendOccurrenceId({ ...opens, track: { ...track, sessionId: '6' } })
    ).toBeUndefined()
    expect(
      getExtendOccurrenceId({
        ...opens,
        track: { ...track, sessionId: undefined },
      })
    ).toBeUndefined()
  })

  test('ignores a loaded occurrence that is not the one the link names', () => {
    expect(
      getExtendOccurrenceId({ ...opens, requestedOccurrenceId: '11' })
    ).toBeUndefined()
  })
})
