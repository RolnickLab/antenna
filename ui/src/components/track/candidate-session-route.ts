/**
 * The session view opened on a merge candidate's frame with both occurrences
 * selected, so their boxes and paths can be compared on the capture itself.
 * Built by hand because `getAppRoute` keeps one value per parameter.
 */
export const getCandidateSessionRoute = ({
  captureId,
  occurrenceIds,
  sessionRoute,
}: {
  captureId: string
  occurrenceIds: string[]
  /** The session page's path, from `APP_ROUTES.SESSION_DETAILS`. */
  sessionRoute: string
}): string => {
  const params = new URLSearchParams()
  occurrenceIds.forEach((id) => params.append('occurrence', id))
  params.set('capture', captureId)

  return `${sessionRoute}?${params}`
}
