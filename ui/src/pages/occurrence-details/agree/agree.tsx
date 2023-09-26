import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { Button } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'

interface AgreeProps {
  agreed?: boolean
  occurrenceId: string
  taxonId: string
}

export const Agree = ({ agreed, occurrenceId, taxonId }: AgreeProps) => {
  const { createIdentification, isLoading, isSuccess } =
    useCreateIdentification()

  if (isSuccess || agreed) {
    return <Button icon={IconType.RadixCheck} label="Agreed" />
  }

  return (
    <Button
      label="Agree"
      loading={isLoading}
      onClick={() => createIdentification({ occurrenceId, taxonId })}
    />
  )
}
