import { useCreateJob } from 'data-services/hooks/jobs/useCreateJob'
import { CaptureDetails } from 'data-services/models/capture-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const ProcessNow = ({
  capture,
  pipelineId,
}: {
  capture?: CaptureDetails
  pipelineId?: string
}) => {
  const { projectId } = useParams()
  const { createJob, isLoading, isSuccess } = useCreateJob()
  const icon = isSuccess ? IconType.RadixCheck : undefined
  const disabled = !capture || capture.hasJobInProgress

  if (disabled) {
    return (
      <Button
        icon={icon}
        disabled
        label={translate(STRING.PROCESS_NOW)}
        loading={isLoading}
        theme={ButtonTheme.Neutral}
      />
    )
  }

  return (
    <Tooltip content={translate(STRING.MESSAGE_PROCESS_NOW_TOOLTIP)}>
      <Button
        icon={icon}
        label={translate(STRING.PROCESS_NOW)}
        loading={isLoading}
        theme={ButtonTheme.Neutral}
        onClick={() => {
          createJob({
            delay: 1,
            name: `Capture #${capture.id}`,
            sourceImage: capture.id,
            pipeline: pipelineId,
            projectId: projectId as string,
            startNow: true,
          })
        }}
      />
    </Tooltip>
  )
}
