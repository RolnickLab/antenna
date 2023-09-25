import { useUserInfo } from 'data-services/hooks/auth/useUserInfo'
import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { OccurrenceDetails } from 'data-services/models/occurrence-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'

interface AgreeProps {
  buttonTheme?: ButtonTheme
  occurrence: OccurrenceDetails
  taxonId: string
}

export const Agree = ({ buttonTheme, occurrence, taxonId }: AgreeProps) => {
  const { userInfo } = useUserInfo()
  const { createIdentification, isLoading, isSuccess } =
    useCreateIdentification()

  if (!userInfo) {
    return null
  }

  const agreed = occurrence.humanIdentifications
    .filter((i) => i.user.id === userInfo.id)
    .some((i) => !i.overridden && i.taxon.id === taxonId)

  if (agreed) {
    return null
  }

  if (isSuccess) {
    return (
      <Button icon={IconType.RadixCheck} label="Agreed" theme={buttonTheme} />
    )
  }

  return (
    <Button
      label="Agree"
      loading={isLoading}
      theme={buttonTheme}
      onClick={() =>
        createIdentification({ occurrenceId: occurrence.id, taxonId })
      }
    />
  )
}
