import { IdentificationFieldValues } from 'data-services/hooks/identifications/types'
import { useCreateIdentifications } from 'data-services/hooks/identifications/useCreateIdentifications'
import { Occurrence } from 'data-services/models/occurrence'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { IdQuickActions } from 'pages/occurrence-details/reject-id/id-quick-actions'
import { useMemo } from 'react'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { useUserInfo } from 'utils/user/userInfoContext'

export const OccurrenceActions = ({
  occurrences = [],
}: {
  occurrences?: Occurrence[]
}) => {
  const { userInfo } = useUserInfo()

  const allAgreed = !occurrences.some((occurrence) => {
    const agreed = userInfo ? occurrence.userAgreed(userInfo.id) : false

    return !agreed
  })

  const canUpdate = occurrences[0]?.userPermissions.includes(
    UserPermission.Update
  )

  if (!canUpdate) {
    return null
  }

  return (
    <>
      <Agree allAgreed={allAgreed} occurrences={occurrences} />
      <IdQuickActions
        occurrenceIds={occurrences.map((occurrence) => occurrence.id)}
        occurrenceTaxons={occurrences.map(
          (occurrence) => occurrence.determinationTaxon
        )}
      />
    </>
  )
}

const Agree = ({
  occurrences = [],
  allAgreed,
}: {
  occurrences?: Occurrence[]
  allAgreed: boolean
}) => {
  const { userInfo } = useUserInfo()

  const agreeParams: IdentificationFieldValues[] = useMemo(
    () =>
      occurrences
        .filter((occurrences) => {
          const agreed = userInfo?.id
            ? userInfo.id === occurrences.determinationVerifiedBy?.id
            : false

          return !agreed
        })
        .map((occurrence) => ({
          agreeWith: {
            identificationId: occurrence.determinationIdentificationId,
            predictionId: occurrence.determinationPredictionId,
          },
          occurrenceId: occurrence.id,
          taxonId: occurrence.determinationTaxon.id,
        })),
    [occurrences]
  )

  const { createIdentifications, isLoading, isSuccess, error } =
    useCreateIdentifications(agreeParams)

  if (isSuccess || allAgreed) {
    return (
      <Button
        label={translate(STRING.AGREED)}
        icon={IconType.RadixCheck}
        disabled
      />
    )
  }

  return (
    <Tooltip content={error} contentStyle={{ zIndex: 3 }}>
      <Button
        icon={error ? IconType.Error : undefined}
        label={translate(STRING.AGREE)}
        loading={isLoading}
        theme={error ? ButtonTheme.Error : undefined}
        onClick={createIdentifications}
      />
    </Tooltip>
  )
}
