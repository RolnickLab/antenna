import { STRING, translate } from 'utils/language'

/**
 * The name to show for the author of an action. "Anonymous" is kept for actions with no user, so
 * a signed-in user who has not set a display name reads as "You" to themselves and as unnamed to
 * others. The viewer's own name is read from their profile, since `user.name` may already be a label.
 */
export const getUserLabel = (
  user?: { id?: string | number; name?: string | null } | null,
  currentUser?: { id: string; name?: string }
) => {
  if (!user) {
    return translate(STRING.ANONYMOUS_USER)
  }

  const isCurrentUser =
    !!currentUser && user.id !== undefined && `${user.id}` === currentUser.id

  if (isCurrentUser && !currentUser.name?.length) {
    return translate(STRING.YOU)
  }

  return user.name?.length ? user.name : translate(STRING.UNNAMED_USER)
}
