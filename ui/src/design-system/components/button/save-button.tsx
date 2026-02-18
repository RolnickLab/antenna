import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const SaveButton = ({
  isLoading,
  isSuccess,
  onClick,
}: {
  isLoading?: boolean
  isSuccess?: boolean
  onClick?: () => void
}) => (
  <Button onClick={onClick} size="small" type="submit" variant="success">
    <span>{isSuccess ? translate(STRING.SAVED) : translate(STRING.SAVE)}</span>
    {isSuccess ? (
      <CheckIcon className="w-4 h-4" />
    ) : isLoading ? (
      <Loader2Icon className="w-4 h-4 animate-spin" />
    ) : null}
  </Button>
)
