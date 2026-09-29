import { UserPermission } from 'utils/user/types'

export interface TrackEditRights {
  /** Split, merge, move and extend a track. */
  canRestructure: boolean
  /** Confirm or withdraw a track's grouping. */
  canVerify: boolean
}

/**
 * Mirrors the server: restructuring needs the occurrence delete right, confirming
 * either right. See #1272.
 */
export const getTrackEditRights = (
  userPermissions: UserPermission[] = []
): TrackEditRights => {
  const canRestructure = userPermissions.includes(UserPermission.Delete)

  return {
    canRestructure,
    canVerify:
      canRestructure || userPermissions.includes(UserPermission.Update),
  }
}
