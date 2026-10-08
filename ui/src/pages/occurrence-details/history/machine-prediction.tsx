import { ErrorState } from 'components/error-state/error-state'
import { TaxonDetails } from 'components/taxon-details/taxon-details'
import { useClassificationDetails } from 'data-services/hooks/identifications/useClassificationDetails'
import {
  MachinePrediction as Identification,
  OccurrenceDetails as Occurrence,
} from 'data-services/models/occurrence-details'
import { Taxon } from 'data-services/models/taxa'
import { Loader2 } from 'lucide-react'
import {
  BasicTooltip,
  Collapsible,
  IdentificationCard,
  IdentificationDetails,
  IdentificationScore,
} from 'nova-ui-kit'
import { ReactNode, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { EntityRef } from 'utils/entity-references'
import { UserInfo, UserPermission } from 'utils/user/types'
import { Agree } from '../agree/agree'
import { EntityRefValue } from 'components/entity-ref-value/entity-ref-value'
import { HistoryStats } from './history-stats'
import machineAvatar from './machine-avatar.svg'

export const MachinePrediction = ({
  avatar,
  avatarTooltip,
  children,
  currentUser,
  identification,
  job,
  occurrence,
  subTitle,
  timestamp,
  title,
}: {
  /** Header overrides for a card that shows a run's prediction rather than a classifier's. */
  avatar?: ReactNode
  avatarTooltip?: string
  /** Details shown below the other predictions when the card is expanded. */
  children?: ReactNode
  currentUser?: UserInfo
  identification: Identification
  /** The job that wrote the prediction, shown as a row when the history names one. */
  job?: EntityRef
  occurrence: Occurrence
  /** Replaces the terminal/intermediate label. */
  subTitle?: string
  timestamp?: string
  title?: string
}) => {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()
  const { projectId } = useParams()
  const formattedTime = getFormatedDateTimeString({
    date: new Date(timestamp ?? identification.createdAt),
  })

  return (
    <div>
      <span className="block mb-2 mr-2 text-right text-muted-foreground body-overline-small normal-case">
        {formattedTime}
      </span>
      <IdentificationCard
        avatar={
          <BasicTooltip
            content={avatarTooltip ?? translate(STRING.MACHINE_PREDICTION)}
          >
            <span className="flex items-center justify-center">
              {avatar ?? <img alt="" src={machineAvatar} />}
            </span>
          </BasicTooltip>
        }
        collapsible
        collapsibleTriggerTooltip={getExpandTooltip(open)}
        onOpenChange={setOpen}
        open={open}
        subTitle={
          subTitle ??
          (identification.terminal
            ? translate(STRING.TERMINAL_CLASSIFICATION)
            : translate(STRING.INTERMEDIATE_CLASSIFICATION))
        }
        title={
          title ??
          identification.algorithm?.name ??
          translate(STRING.MACHINE_SUGGESTION)
        }
        onTitleClick={
          identification.algorithm
            ? () =>
                navigate(
                  APP_ROUTES.ALGORITHM_DETAILS({
                    projectId: projectId as string,
                    algorithmId: identification.algorithm?.id,
                  })
                )
            : undefined
        }
      >
        <AgreeablePredictionRow
          applied={identification.applied}
          currentUser={currentUser}
          occurrence={occurrence}
          predictionId={identification.id}
          score={identification.score}
          taxon={identification.taxon}
        />
        <Collapsible.Root open={open} onOpenChange={setOpen}>
          <Collapsible.Content>
            <MorePredictions
              currentUser={currentUser}
              occurrence={occurrence}
              open={open}
              predictionId={identification.id}
              shownTaxonId={identification.taxon.id}
              showEmpty={!children}
            />
            {job ? (
              <HistoryStats
                stats={[
                  {
                    label: translate(STRING.FIELD_LABEL_JOB),
                    value: (
                      <EntityRefValue
                        projectId={projectId as string}
                        reference={job}
                      />
                    ),
                  },
                ]}
              />
            ) : null}
            {children}
          </Collapsible.Content>
        </Collapsible.Root>
      </IdentificationCard>
    </div>
  )
}

const PredictionRow = ({
  applied,
  children,
  score,
  taxon,
}: {
  applied?: boolean
  children?: ReactNode
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
              score: `${score}`,
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

const AgreeablePredictionRow = ({
  applied,
  currentUser,
  occurrence,
  predictionId,
  score,
  taxon,
}: {
  applied?: boolean
  currentUser?: UserInfo
  occurrence: Occurrence
  predictionId: string
  score: number
  taxon: Taxon
}) => (
  <PredictionRow applied={applied} score={score} taxon={taxon}>
    {occurrence.userPermissions.includes(UserPermission.Update) && (
      <Agree
        agreed={
          currentUser ? occurrence.userAgreed(currentUser.id, taxon.id) : false
        }
        agreeWith={{ predictionId }}
        applied={applied}
        occurrenceId={occurrence.id}
        taxonId={taxon.id}
      />
    )}
  </PredictionRow>
)

/** The runner-up taxa of a classification, loaded when its card is expanded. */
const MorePredictions = ({
  currentUser,
  occurrence,
  open,
  predictionId,
  showEmpty = true,
  shownTaxonId,
}: {
  currentUser?: UserInfo
  occurrence: Occurrence
  open: boolean
  predictionId: string
  showEmpty?: boolean
  /** The taxon the card already shows, left out of the list. */
  shownTaxonId: string
}) => {
  const { classification, error, isLoading } = useClassificationDetails(
    predictionId,
    open
  )
  const topN = classification?.topN.filter(
    ({ taxon }) => taxon.id !== shownTaxonId
  )

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
          error={{ message: translate(STRING.PREDICTIONS_NOT_LOADED) }}
        />
      </div>
    )
  }

  if (topN && topN.length === 0) {
    return showEmpty ? (
      <div className="py-6 px-4 border-border border-t text-center text-muted-foreground">
        <span className="body-small">
          {translate(STRING.NO_MORE_PREDICTIONS)}
        </span>
      </div>
    ) : null
  }

  return (
    <>
      {topN?.map(({ score, taxon }) => (
        <AgreeablePredictionRow
          key={taxon.id}
          applied={taxon.id === occurrence.determinationTaxon.id}
          currentUser={currentUser}
          occurrence={occurrence}
          predictionId={predictionId}
          score={score}
          taxon={taxon}
        />
      ))}
    </>
  )
}

const getExpandTooltip = (open: boolean) =>
  translate(
    open
      ? STRING.FEWER_PREDICTIONS_AND_DETAILS
      : STRING.MORE_PREDICTIONS_AND_DETAILS
  )
