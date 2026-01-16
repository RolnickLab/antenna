import classNames from 'classnames'
import { EmptyState } from 'components/empty-state/empty-state'
import { ErrorState } from 'components/error-state/error-state'
import galleryStyles from 'components/gallery/gallery.module.scss'
import { Occurrence } from 'data-services/models/occurrence'
import { Taxon } from 'data-services/models/taxa'
import cardStyles from 'design-system/components/card/card.module.scss'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { CheckIcon } from 'lucide-react'
import { Button, IdentificationScore } from 'nova-ui-kit'
import { Agree } from 'pages/occurrence-details/agree/agree'
import { IdQuickActions } from 'pages/occurrence-details/id-quick-actions/id-quick-actions'
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
  items = [],
  onSelectedItemsChange,
  selectable,
  selectedItems,
}: {
  error?: any
  isLoading: boolean
  items?: Occurrence[]
  onSelectedItemsChange?: (selectedItems: string[]) => void
  selectable?: boolean
  selectedItems: string[]
}) => {
  const isSelecting = selectedItems?.length > 0
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

  if (items.length === 0) {
    return <EmptyState />
  }

  return (
    <div className="pt-4">
      <MultiSelectButton
        items={items}
        selectedItems={selectedItems}
        onSelectedItemsChange={onSelectedItemsChange}
      />
      <div className={classNames(galleryStyles.gallery)}>
        {items.map((item) => {
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
          const checked = selectedItems.includes(item.id)
          const onCheckedToggle = () => {
            onSelectedItemsChange?.(
              !checked
                ? [...selectedItems, item.id]
                : selectedItems.filter((id) => id !== item.id)
            )
          }

          return (
            <div
              key={item.id}
              className="flex flex-col bg-background border border-border rounded-lg overflow-hidden"
            >
              <div className="aspect-square border-b border-border group relative">
                {isSelecting ? (
                  <div
                    className="w-full h-full relative cursor-pointer"
                    onClick={onCheckedToggle}
                  >
                    {image ? (
                      <img src={image.src} className={cardStyles.image} />
                    ) : (
                      <div className={cardStyles.image}>
                        <Icon
                          type={IconType.Photograph}
                          theme={IconTheme.Neutral}
                          size={32}
                        />
                      </div>
                    )}
                  </div>
                ) : (
                  <Link className="w-full h-full relative" to={detailsRoute}>
                    {image ? (
                      <img src={image.src} className={cardStyles.image} />
                    ) : (
                      <div className={cardStyles.image}>
                        <Icon
                          type={IconType.Photograph}
                          theme={IconTheme.Neutral}
                          size={32}
                        />
                      </div>
                    )}
                  </Link>
                )}
                {selectable ? (
                  <div
                    className={classNames(
                      'absolute top-2 left-2 group-hover:visible',
                      { invisible: !isSelecting }
                    )}
                  >
                    <Button
                      className={classNames('hover:text-opacity-100', {
                        'text-opacity-0': !checked,
                        'group-hover:text-opacity-100': isSelecting,
                      })}
                      onClick={onCheckedToggle}
                      size="icon"
                      variant={checked ? 'default' : 'outline'}
                    >
                      <CheckIcon className="w-4 h-4" />
                    </Button>
                  </div>
                ) : null}
              </div>
              <div className="grow flex flex-col justify-between gap-2 p-4">
                <div className="flex items-center gap-2">
                  <Link to={detailsRoute}>
                    <span
                      className={classNames(
                        'body-base font-medium text-primary',
                        {
                          italic: isGenusOrBelow(item.determinationTaxon),
                        }
                      )}
                    >
                      {item.determinationTaxon.name}
                    </span>
                  </Link>
                </div>
                <div className="flex flex-wrap items-center justify-start gap-2">
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
                  {!isSelecting && canUpdate && (
                    <>
                      <Agree
                        agreed={agreed}
                        agreeWith={{
                          identificationId: item.determinationIdentificationId,
                          predictionId: item.determinationPredictionId,
                        }}
                        applied
                        compact
                        occurrenceId={item.id}
                        taxonId={item.determinationTaxon.id}
                      />
                      <SuggestIdPopover occurrenceIds={[item.id]} />
                      <IdQuickActions
                        occurrenceIds={[item.id]}
                        occurrenceTaxa={[item.determinationTaxon]}
                        zIndex={1}
                      />
                    </>
                  )}
                </div>
              </div>
            </div>
          )
        })}
        {!isLoading && items.length === 0 && <EmptyState />}
      </div>
    </div>
  )
}

interface MultiSelectButtonProps {
  items: Occurrence[]
  selectedItems?: string[]
  onSelectedItemsChange?: (selectedItems: string[]) => void
}

const MultiSelectButton = ({
  items = [],
  selectedItems,
  onSelectedItemsChange,
}: MultiSelectButtonProps) => {
  const deselectAll = () => onSelectedItemsChange?.([])
  const selectAll = () => onSelectedItemsChange?.(items.map((item) => item.id))

  const allSelected =
    selectedItems?.length && selectedItems.length === items.length

  return (
    <Button
      onClick={() => {
        if (allSelected) {
          deselectAll()
        } else {
          selectAll()
        }
      }}
      size="small"
      variant="outline"
    >
      <span>{allSelected ? 'Deselect all' : 'Select all'}</span>
    </Button>
  )
}
