import {
  MachinePrediction as Identification,
  OccurrenceDetails as Occurrence,
} from 'data-services/models/occurrence-details'
import {
  IdentificationCard,
  IdentificationDetails,
  IdentificationStatus,
  TaxonDetails,
} from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { UserInfo } from 'utils/user/types'

export const MachinePrediction = ({
  identification,
}: {
  currentUser?: UserInfo
  identification: Identification
  occurrence: Occurrence
}) => (
  <IdentificationCard
    avatar={<></>}
    onOpenChange={() => {}}
    open
    title={
      identification.algorithm?.name ?? translate(STRING.MACHINE_SUGGESTION)
    }
  >
    <IdentificationDetails
      className="border-border border-t"
      status={identification.applied ? 'confirmed' : 'unconfirmed'}
    >
      <IdentificationStatus
        confidenceScore={identification.score}
        status={identification.applied ? 'confirmed' : 'unconfirmed'}
      />
      <TaxonDetails compact taxon={identification.taxon} withTooltips />
    </IdentificationDetails>
  </IdentificationCard>
)
