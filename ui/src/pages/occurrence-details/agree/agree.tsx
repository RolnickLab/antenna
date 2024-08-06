import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { useEffect } from 'react'
import { STRING, translate } from 'utils/language'

interface AgreeProps {
  agreed?: boolean
  agreeWith: {
    identificationId?: string
    predictionId?: string
  }
  buttonTheme?: ButtonTheme
  occurrenceId: string
  taxonId: string
}

export const Agree = ({
  agreed,
  agreeWith,
  buttonTheme,
  occurrenceId,
  taxonId,
}: AgreeProps) => {
  const { createIdentification, isLoading, isSuccess, error, reset } =
    useCreateIdentification()

  useEffect(() => {
    reset()
  }, [agreed])

  if (isSuccess || agreed) {
    return (
      <Button
        label={translate(STRING.AGREED)}
        icon={IconType.RadixCheck}
        theme={buttonTheme}
        disabled
      />
    )
  }

  return (
    <Tooltip content={error}>
      <Button
        icon={error ? IconType.Error : undefined}
        label={translate(STRING.AGREE)}
        loading={isLoading}
        theme={error ? ButtonTheme.Error : buttonTheme}
        onClick={() =>
          createIdentification({
            agreeWith,
            occurrenceId,
            taxonId,
          })
        }
      />
    </Tooltip>
  )
}
