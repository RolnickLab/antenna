import { useCreateIdentification } from 'data-services/hooks/identifications/useCreateIdentification'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { AlertCircleIcon, CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useEffect } from 'react'
import { STRING, translate } from 'utils/language'

interface AgreeProps {
  agreed?: boolean
  agreeWith: {
    identificationId?: string
    predictionId?: string
  }
  occurrenceId: string
  taxonId: string
}

export const Agree = ({
  agreed,
  agreeWith,
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
        className="text-primary-600"
        disabled
        size="small"
        variant="outline"
      >
        <CheckIcon className="w-4 h-4" />
        {translate(STRING.AGREED)}
      </Button>
    )
  }

  return (
    <BasicTooltip asChild content={error}>
      <Button
        className="text-primary-600"
        loading={isLoading}
        size="small"
        variant="outline"
        onClick={() =>
          createIdentification({
            agreeWith,
            occurrenceId,
            taxonId,
          })
        }
      >
        {isLoading ? (
          <Loader2Icon className="w-4 h-4 animate-spin" />
        ) : error ? (
          <AlertCircleIcon className="w-4 h-4 text-destructive" />
        ) : null}
        {translate(STRING.AGREE)}
      </Button>
    </BasicTooltip>
  )
}
