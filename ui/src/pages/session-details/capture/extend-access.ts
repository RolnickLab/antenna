import { getTrackEditRights } from 'pages/occurrence-details/track/track-edit-rights'
import { UserPermission } from 'utils/user/types'

interface RequestedTrack {
  id: string
  sessionId?: string
  userPermissions: UserPermission[]
}

/**
 * The occurrence extend mode may open on, or undefined. A link can name an occurrence
 * the viewer may not edit, or one from another session, and both are ignored.
 */
export const getExtendOccurrenceId = ({
  enabled,
  requestedOccurrenceId,
  sessionId,
  track,
}: {
  enabled: boolean
  requestedOccurrenceId?: string
  sessionId?: string
  /** The requested occurrence, once loaded. */
  track?: RequestedTrack
}) => {
  if (!enabled || !requestedOccurrenceId || !track || !sessionId) {
    return undefined
  }

  if (track.id !== requestedOccurrenceId || track.sessionId !== sessionId) {
    return undefined
  }

  return getTrackEditRights(track.userPermissions).canRestructure
    ? requestedOccurrenceId
    : undefined
}
