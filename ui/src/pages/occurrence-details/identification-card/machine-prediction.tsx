import { ErrorState } from 'components/error-state/error-state'
import { useClassificationDetails } from 'data-services/hooks/identifications/useClassificationDetails'
import {
  MachinePrediction as Identification,
  OccurrenceDetails as Occurrence,
} from 'data-services/models/occurrence-details'
import { Taxon } from 'data-services/models/taxa'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { Loader2 } from 'lucide-react'
import {
  Collapsible,
  IdentificationCard,
  IdentificationDetails,
  IdentificationScore,
  TaxonDetails,
} from 'nova-ui-kit'
import { ReactNode, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { UserInfo, UserPermission } from 'utils/user/types'
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
  const { classification, error, isLoading } = useClassificationDetails(
    identification.id,
    open
  )
  const topN = classification?.topN.filter(
    ({ taxon }) => taxon.id !== identification.taxon.id
  )
  const formattedTime = getFormatedDateTimeString({
    date: new Date(identification.createdAt),
  })
  const showAgree = occurrence.userPermissions.includes(UserPermission.Update)

  return (
    <div>
      <span className="block mb-2 mr-2 text-right text-muted-foreground body-overline-small normal-case">
        {formattedTime}
      </span>
      <IdentificationCard
        avatar={<img alt="" src={machineAvatar} />}
        collapsible
        collapsibleTriggerTooltip={
          open ? 'Hide top predictions' : 'Show top predictions'
        }
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
          {showAgree && (
            <Agree
              agreed={
                currentUser
                  ? occurrence.userAgreed(
                      currentUser.id,
                      identification.taxon.id
                    )
                  : false
              }
              agreeWith={{ predictionId: identification.id }}
              applied={identification.applied}
              occurrenceId={occurrence.id}
              taxonId={identification.taxon.id}
            />
          )}
        </MachinePredictionDetails>
        <Collapsible.Root open={open} onOpenChange={setOpen}>
          <Collapsible.Content>
            <FetchDetails
              empty={topN && topN.length === 0}
              error={error}
              isLoading={isLoading}
            />
            {topN?.map(({ score, taxon }) => {
              const applied = taxon.id === occurrence.determinationTaxon.id

              return (
                <MachinePredictionDetails
                  key={taxon.id}
                  applied={applied}
                  score={score}
                  taxon={taxon}
                >
                  {showAgree && (
                    <Agree
                      agreed={
                        currentUser
                          ? occurrence.userAgreed(currentUser.id, taxon.id)
                          : false
                      }
                      agreeWith={{ predictionId: identification.id }}
                      applied={applied}
                      occurrenceId={occurrence.id}
                      taxonId={taxon.id}
                    />
                  )}
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
}) => {
  const { projectId } = useParams()

  return (
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
          <Link
            to={getAppRoute({
              to: APP_ROUTES.TAXON_DETAILS({
                projectId: projectId as string,
                taxonId: taxon.id,
              }),
            })}
          >
            <TaxonDetails compact taxon={taxon} />
          </Link>
        </div>
        {children}
      </div>
    </IdentificationDetails>
  )
}

const FetchDetails = ({
  empty,
  error,
  isLoading,
}: {
  empty?: boolean
  error: unknown
  isLoading: boolean
}) => {
  if (isLoading) {
    return (
      <div className="flex justify-center py-6 px-4 border-border border-t text-center">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex justify-center py-6 px-4 border-border border-t text-center">
        <ErrorState
          compact
          error={{ message: 'Could not load classification details' }}
        />
      </div>
    )
  }

  if (empty) {
    return (
      <div className="py-6 px-4 border-border border-t text-center text-muted-foreground">
        <span className="body-small">No classification details to show</span>
      </div>
    )
  }

  return null
}
