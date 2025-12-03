import classNames from 'classnames'
import { usePopulateProcessingService } from 'data-services/hooks/processing-services/usePopulateProcessingService'
import { ProcessingService } from 'data-services/models/processing-service'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { AlertCircleIcon, Loader2 } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const PopulateProcessingService = ({
  processingService,
}: {
  processingService: ProcessingService
}) => {
  const { populateProcessingService, isLoading, error } =
    usePopulateProcessingService()

  return (
    <BasicTooltip
      asChild
      content={
        error
          ? 'Could not register the pipelines, please check the endpoint URL.'
          : undefined
      }
    >
      <Button
        className={classNames({ 'text-destructive': error })}
        disabled={isLoading}
        onClick={() => populateProcessingService(processingService.id)}
        size="small"
        variant="outline"
      >
        {error ? <AlertCircleIcon className="w-4 h-4" /> : null}
        <span>{translate(STRING.REGISTER_PIPELINES)}</span>
        {isLoading ? <Loader2 className="w-4 h-4 ml-2 animate-spin" /> : null}
      </Button>
    </BasicTooltip>
  )
}
