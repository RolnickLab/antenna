import { useClassificationDetails } from 'data-services/hooks/identifications/useClassificationDetails'
import {
  MachinePrediction as Identification,
  OccurrenceDetails as Occurrence,
} from 'data-services/models/occurrence-details'
import {
  Collapsible,
  IdentificationCard,
  IdentificationDetails,
  IdentificationStatus,
  TaxonDetails,
} from 'nova-ui-kit'
import { useState } from 'react'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { UserInfo } from 'utils/user/types'
import machineAvatar from './machine-avatar.svg'

export const MachinePrediction = ({
  identification,
  occurrence,
}: {
  currentUser?: UserInfo
  identification: Identification
  occurrence: Occurrence
}) => {
  const [open, setOpen] = useState(false)
  const { classification } = useClassificationDetails(identification.id, open)
  const formattedTime = getFormatedDateTimeString({
    date: new Date(identification.createdAt),
  })

  return (
    <div>
      <span className="block mb-2 mr-2 text-right text-muted-foreground body-overline-small normal-case">
        {formattedTime}
      </span>
      <IdentificationCard
        avatar={<img alt="" src={machineAvatar} />}
        collapsible
        onOpenChange={setOpen}
        open={open}
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
        <Collapsible.Root open={open} onOpenChange={setOpen}>
          <Collapsible.Content>
            {classification?.topN
              .filter(({ taxon }) => taxon.id !== identification.taxon.id)
              .map(({ score, taxon }) => {
                const applied = taxon.id === occurrence.determinationTaxon.id

                return (
                  <IdentificationDetails
                    className="border-border border-t"
                    status={applied ? 'confirmed' : 'unconfirmed'}
                  >
                    <IdentificationStatus
                      confidenceScore={score}
                      status={applied ? 'confirmed' : 'unconfirmed'}
                    />
                    <TaxonDetails compact taxon={taxon} withTooltips />
                  </IdentificationDetails>
                )
              })}
          </Collapsible.Content>
        </Collapsible.Root>
      </IdentificationCard>
    </div>
  )
}
