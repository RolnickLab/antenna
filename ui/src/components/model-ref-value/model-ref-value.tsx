import { Link } from 'react-router-dom'
import {
  ServerModelRef,
  getModelRefLabel,
  linkFor,
} from 'utils/model-references'

/** A record the API names: a link to its page, or plain text when it was deleted or has no page. */
export const ModelRefValue = ({
  projectId,
  reference,
}: {
  projectId: string
  reference: ServerModelRef
}) => {
  const to = linkFor(reference, projectId)
  const label = getModelRefLabel(reference)

  return to ? (
    <Link className="underline underline-offset-4" to={to}>
      {label}
    </Link>
  ) : (
    <>{label}</>
  )
}
