import classNames from 'classnames'
import { usePopulateCaptureSet } from 'data-services/hooks/capture-sets/usePopulateCaptureSet'
import { CaptureSet } from 'data-services/models/capture-set'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { AlertCircleIcon, Loader2, RefreshCcwIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const PopulateCaptureSet = ({
  captureSet,
}: {
  captureSet: CaptureSet
}) => {
  const { populateCaptureSet, isLoading, error } = usePopulateCaptureSet()

  return (
    <BasicTooltip
      asChild
      content={
        error
          ? 'Could not populate the capture set, please retry.'
          : translate(STRING.POPULATE)
      }
    >
      <Button
        aria-label={translate(STRING.POPULATE)}
        className={classNames({ 'text-destructive': error })}
        disabled={isLoading}
        onClick={() => populateCaptureSet(captureSet.id)}
        size="icon"
        variant="ghost"
      >
        {error ? (
          <AlertCircleIcon className="w-4 h-4" />
        ) : isLoading ? (
          <Loader2 className="w-4 h-4 ml-2 animate-spin" />
        ) : (
          <RefreshCcwIcon className="w-4 h-4" />
        )}
      </Button>
    </BasicTooltip>
  )
}
