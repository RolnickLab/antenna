import { useClassificationDetails } from 'data-services/hooks/identifications/useClassificationDetails'
import {
  MachinePrediction as Identification,
  OccurrenceDetails as Occurrence,
} from 'data-services/models/occurrence-details'
import { Taxon } from 'data-services/models/taxa'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import {
  Collapsible,
  IdentificationCard,
  IdentificationDetails,
  IdentificationScore,
  TaxonDetails,
} from 'nova-ui-kit'
import { ReactNode, useState } from 'react'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { UserInfo } from 'utils/user/types'
import { Agree } from '../agree/agree'
import machineAvatar from './machine-avatar.svg'

export const MachinePrediction = ({
  currentUser,
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
        subTitle={
          identification.terminal
            ? translate(STRING.TERMINAL_CLASSIFICATION)
            : translate(STRING.INTERMEDIATE_CLASSIFICATION)
        }
        title={
          identification.algorithm?.name ?? translate(STRING.MACHINE_SUGGESTION)
        }
      >
        <MachinePredictionDetails
          applied={identification.applied}
          score={identification.score}
          taxon={identification.taxon}
        >
          {
            <Agree
              agreeWith={{ predictionId: identification.id }}
              occurrenceId={occurrence.id}
              taxonId={identification.taxon.id}
            />
          }
        </MachinePredictionDetails>
        <Collapsible.Root open={open} onOpenChange={setOpen}>
          <Collapsible.Content>
            {classification?.topN
              .filter(({ taxon }) => taxon.id !== identification.taxon.id)
              .map(({ score, taxon }) => {
                const applied = taxon.id === occurrence.determinationTaxon.id

                return (
                  <MachinePredictionDetails
                    applied={applied}
                    score={score}
                    taxon={taxon}
                  >
                    <Agree
                      agreed={
                        currentUser
                          ? occurrence.userAgreed(currentUser.id, taxon.id)
                          : false
                      }
                      agreeWith={{ predictionId: identification.id }}
                      occurrenceId={occurrence.id}
                      taxonId={taxon.id}
                    />
                  </MachinePredictionDetails>
                )
              })}
          </Collapsible.Content>
        </Collapsible.Root>
      </IdentificationCard>
    </div>
  )
}

const MachinePredictionDetails = ({
  applied,
  children,
  score,
  taxon,
}: {
  applied?: boolean
  children: ReactNode
  score: number
  taxon: Taxon
}) => (
  <IdentificationDetails applied={applied} className="border-border border-t">
    <div className="w-full flex flex-col items-end gap-4">
      <div className="w-full flex items-center gap-4">
        <BasicTooltip
          content={translate(STRING.MACHINE_PREDICTION_SCORE, {
            score,
          })}
        >
          <div className="px-1">
            <IdentificationScore confidenceScore={score} />
          </div>
        </BasicTooltip>
        <TaxonDetails compact taxon={taxon} withTooltips />
      </div>
      {children}
    </div>
  </IdentificationDetails>
)
