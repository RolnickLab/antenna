import classNames from 'classnames'
import { EmptyState } from 'components/empty-state/empty-state'
import { ErrorState } from 'components/error-state/error-state'
import galleryStyles from 'components/gallery/gallery.module.scss'
import { Occurrence } from 'data-services/models/occurrence'
import { Taxon } from 'data-services/models/taxa'
import cardStyles from 'design-system/components/card/card.module.scss'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { IdentificationScore } from 'nova-ui-kit'
import { Agree } from 'pages/occurrence-details/agree/agree'
import { IdQuickActions } from 'pages/occurrence-details/reject-id/id-quick-actions'
import { SuggestIdPopover } from 'pages/occurrence-details/suggest-id/suggest-id-popover'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { useUserInfo } from 'utils/user/userInfoContext'

export const isGenusOrBelow = (taxon: Taxon) =>
  taxon.rank === 'GENUS' ||
  taxon.rank === 'SPECIES' ||
  taxon.rank === 'SUBSPECIES'

export const OccurrenceGallery = ({
  error,
  isLoading,
  occurrences = [],
}: {
  error?: any
  isLoading: boolean
  occurrences?: Occurrence[]
}) => {
  const showQuickActions = true
  const { projectId } = useParams()
  const { userInfo } = useUserInfo()

  if (isLoading) {
    return (
      <div className={galleryStyles.loadingWrapper}>
        <LoadingSpinner />
      </div>
    )
  }

  if (error) {
    return <ErrorState error={error} />
  }

  if (occurrences.length === 0) {
    return <EmptyState />
  }

  return (
    <div className={classNames(galleryStyles.gallery, galleryStyles.large)}>
      {occurrences.map((item) => {
        const detailsRoute = getAppRoute({
          to: APP_ROUTES.OCCURRENCE_DETAILS({
            projectId: projectId as string,
            occurrenceId: item.id,
          }),
          keepSearchParams: true,
        })
        const image = item.images[0]
        const canUpdate = item.userPermissions.includes(UserPermission.Update)
        const agreed = userInfo ? item.userAgreed(userInfo.id) : false

        return (
          <div
            key={item.id}
            className="flex flex-col bg-background border border-border rounded-lg"
          >
            <div className="aspect-square border-b border-border relative">
              <img src={image.src} className={cardStyles.image} />
            </div>
            <div className="grow flex flex-col justify-between gap-2 p-4">
              <div className="flex items-center gap-2">
                {item.determinationScore !== undefined ? (
                  <BasicTooltip
                    content={
                      item.determinationVerified
                        ? translate(STRING.VERIFIED_BY, {
                            name: item.determinationVerifiedBy?.name,
                          })
                        : translate(STRING.MACHINE_PREDICTION_SCORE, {
                            score: `${item.determinationScore}`,
                          })
                    }
                  >
                    <IdentificationScore
                      confirmed={item.determinationVerified}
                      confidenceScore={item.determinationScore}
                    />
                  </BasicTooltip>
                ) : null}
                <Link to={detailsRoute}>
                  <span
                    className={classNames(
                      'body-large font-medium text-primary',
                      {
                        italic: isGenusOrBelow(item.determinationTaxon),
                      }
                    )}
                  >
                    {item.determinationTaxon.name}
                  </span>
                </Link>
              </div>
              {showQuickActions && canUpdate && (
                <div className="flex items-center justify-start gap-2">
                  <Agree
                    agreed={agreed}
                    agreeWith={{
                      identificationId: item.determinationIdentificationId,
                      predictionId: item.determinationPredictionId,
                    }}
                    applied
                    occurrenceId={item.id}
                    taxonId={item.determinationTaxon.id}
                  />
                  <SuggestIdPopover occurrenceIds={[item.id]} />
                  <IdQuickActions
                    occurrenceIds={[item.id]}
                    occurrenceTaxons={[item.determinationTaxon]}
                    zIndex={1}
                  />
                </div>
              )}
            </div>
          </div>
        )
      })}
      {!isLoading && occurrences.length === 0 && <EmptyState />}
    </div>
  )
}
