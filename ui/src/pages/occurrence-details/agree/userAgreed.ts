import { HumanIdentification } from 'data-services/models/occurrence-details'

export const userAgreed = ({
  identifications,
  taxonId,
  userId,
}: {
  identifications: HumanIdentification[]
  taxonId: string
  userId?: string
}) => {
  if (!userId) {
    return false
  }

  return identifications.some((i) => {
    if (i.user.id !== userId) {
      return false
    }
    if (i.overridden) {
      return false
    }
    return i.taxon.id === taxonId
  })
}
