import { IdentificationFieldValues } from 'data-services/hooks/identifications/types'
import { useCreateIdentifications } from 'data-services/hooks/identifications/useCreateIdentifications'
import { Occurrence } from 'data-services/models/occurrence'
import { Button } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
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

  const allAgreed = !occurrences.some((occurrences) => {
    const agreed = userInfo?.id
      ? userInfo.id === occurrences.determinationVerifiedBy?.id
      : false

    return !agreed
  })

  const canUpdate = occurrences[0]?.userPermissions.includes(
    UserPermission.Update
  )

  if (!canUpdate) {
    return null
  }

  return <Agree allAgreed={allAgreed} occurrences={occurrences} />
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

  const { createIdentifications, isLoading, isSuccess } =
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
    <Button
      label={allAgreed ? translate(STRING.AGREED) : translate(STRING.AGREE)}
      loading={isLoading}
      onClick={createIdentifications}
    />
  )
}
