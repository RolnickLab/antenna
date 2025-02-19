import {
  HumanIdentification as Identification,
  OccurrenceDetails as Occurrence,
} from 'data-services/models/occurrence-details'
import {
  IdentificationCard,
  IdentificationDetails,
  IdentificationStatus,
  TaxonDetails,
} from 'nova-ui-kit'
import { UserInfo } from 'utils/user/types'

export const HumanIdentification = ({
  identification,
  user,
}: {
  currentUser?: UserInfo
  identification: Identification
  occurrence: Occurrence
  user: {
    id: string
    image?: string
    name: string
  }
}) => (
  <IdentificationCard
    avatar={user.image?.length ? <img alt="" src={user.image} /> : null}
    onOpenChange={() => {}}
    open
    title={user.name.length ? user.name : 'Anonymous user'}
  >
    <IdentificationDetails
      className="border-border border-t"
      status={identification.applied ? 'confirmed' : 'unconfirmed'}
    >
      <IdentificationStatus
        confidenceScore={1}
        status={identification.applied ? 'confirmed' : 'unconfirmed'}
      />
      <TaxonDetails compact taxon={identification.taxon} withTooltips />
    </IdentificationDetails>
  </IdentificationCard>
)
