import { Link } from 'react-router-dom'
import { EntityRef, getEntityRefLabel, linkFor } from 'utils/entity-references'

/** A record the API names: a link to its page, or plain text when it was deleted or has no page. */
export const EntityRefValue = ({
  projectId,
  reference,
}: {
  projectId: string
  reference: EntityRef
}) => {
  const to = linkFor(reference, projectId)
  const label = getEntityRefLabel(reference)

  return to ? (
    <Link className="underline underline-offset-4" to={to}>
      {label}
    </Link>
  ) : (
    <>{label}</>
  )
}
