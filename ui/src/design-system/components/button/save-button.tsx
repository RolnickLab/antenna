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
  <Button size="small" type="submit" onClick={onClick}>
    <span>{isSuccess ? translate(STRING.SAVED) : translate(STRING.SAVE)}</span>
    {isSuccess ? (
      <CheckIcon className="w-4 h-4 ml-2" />
    ) : isLoading ? (
      <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
    ) : null}
  </Button>
)
