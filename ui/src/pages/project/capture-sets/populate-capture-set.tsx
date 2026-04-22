import classNames from 'classnames'
import { usePopulateCaptureSet } from 'data-services/hooks/capture-sets/usePopulateCaptureSet'
import { CaptureSet } from 'data-services/models/capture-set'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { AlertCircleIcon, Loader2, RefreshCcwIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'
import { parseServerError } from 'utils/parseServerError/parseServerError'

export const PopulateCaptureSet = ({
  captureSet,
  compact,
  variant = 'outline',
}: {
  captureSet: CaptureSet
  compact?: boolean
  variant?: 'ghost' | 'outline'
}) => {
  const { populateCaptureSet, isLoading, error } = usePopulateCaptureSet()

  const tooltip = (() => {
    if (error) {
      return parseServerError(error).message
    }

    if (compact) {
      return translate(STRING.POPULATE)
    }
  })()

  return (
    <BasicTooltip asChild content={tooltip}>
      <Button
        aria-label={translate(STRING.POPULATE)}
        className={classNames({ 'text-destructive': error })}
        disabled={isLoading}
        onClick={() => populateCaptureSet(captureSet.id)}
        size={compact ? 'icon' : 'small'}
        variant={variant}
      >
        {error ? (
          <AlertCircleIcon className="w-4 h-4" />
        ) : isLoading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <RefreshCcwIcon className="w-4 h-4" />
        )}
        {!compact ? <span>{translate(STRING.POPULATE)}</span> : null}
      </Button>
    </BasicTooltip>
  )
}
