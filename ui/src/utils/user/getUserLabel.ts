import { STRING, translate } from 'utils/language'

/**
 * The name to show for the author of an action: their display name, else "Anonymous user". The
 * same rule the identification cards use, so one person reads the same on every card.
 */
export const getUserLabel = (user?: { name?: string | null } | null) =>
  user?.name?.length ? user.name : translate(STRING.ANONYMOUS_USER)
