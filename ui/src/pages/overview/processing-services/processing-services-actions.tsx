import { usePopulateProcessingService } from 'data-services/hooks/processing-services/usePopulateProcessingService'
import { ProcessingService } from 'data-services/models/processing-service'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { STRING, translate } from 'utils/language'

export const PopulateProcessingService = ({
  processingService,
}: {
  processingService: ProcessingService
}) => {
  const { populateProcessingService, isLoading, error } =
    usePopulateProcessingService()

  return (
    <Tooltip
      content={
        error
          ? 'Could not register the pipelines, please check the endpoint URL.'
          : undefined
      }
    >
      <Button
        disabled={isLoading}
        label={translate(STRING.REGISTER_PIPELINES)}
        icon={error ? IconType.Error : undefined}
        loading={isLoading}
        onClick={() => populateProcessingService(processingService.id)}
        theme={error ? ButtonTheme.Error : ButtonTheme.Success}
      />
    </Tooltip>
  )
}
