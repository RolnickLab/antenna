import { usePopulateProcessingService } from 'data-services/hooks/processing-services/usePopulateProcessingService'
import { ProcessingService } from 'data-services/models/processing-service'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'

export const PopulateProcessingService = ({
  processingService,
}: {
  processingService: ProcessingService
}) => {
  const [timestamp, setTimestamp] = useState<string>()
  const { populateProcessingService: populateProcessingService, isLoading } =
    usePopulateProcessingService()

  // TODO: It would be better to inspect task status here, but we currently don't have this information.
  const isPopulating =
    isLoading || timestamp === processingService.updatedAtDetailed

  return (
    <Button
      label={translate(STRING.REGISTER_PIPELINES)}
      loading={isPopulating}
      disabled={isPopulating}
      theme={ButtonTheme.Success}
      onClick={() => {
        populateProcessingService(processingService.id)
        setTimestamp(processingService.updatedAtDetailed)
      }}
    />
  )
}
