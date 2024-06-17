import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { Button } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'

interface RejectIdButtonProps {
  occurrenceId: string
  applied: boolean
  label: string
  value: string
}

export const RejectIdButton = ({
  occurrenceId,
  applied,
  label,
  value,
}: RejectIdButtonProps) => {
  const { createIdentification, isLoading, isSuccess } =
    useCreateIdentification()

  return (
    <Button
      label={label}
      icon={isSuccess || applied ? IconType.RadixCheck : undefined}
      loading={isLoading}
      disabled={isSuccess || applied}
      onClick={() =>
        createIdentification({
          occurrenceId,
          taxonId: value,
        })
      }
    />
  )
}
