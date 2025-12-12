import { useCreateJob } from 'data-services/hooks/jobs/useCreateJob'
import { CaptureDetails } from 'data-services/models/capture-details'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'

export const ProcessNow = ({
  capture,
  pipelineId,
}: {
  capture?: CaptureDetails
  pipelineId?: string
}) => {
  const { projectId } = useParams()
  const { createJob, isLoading, isSuccess } = useCreateJob()
  const canProcess = capture?.userPermissions.includes(
    UserPermission.RunSingleImage
  )
  const disabled =
    !capture || capture.hasJobInProgress || !pipelineId || !canProcess

  // @TODO: hasJobInProgress, replace with if pipeline is healthy/available

  const tooltipContent = canProcess
    ? translate(STRING.MESSAGE_PROCESS_NOW_TOOLTIP)
    : translate(STRING.MESSAGE_PERMISSIONS_MISSING)

  return (
    <BasicTooltip asChild content={tooltipContent}>
      <Button
        className="rounded-md !bg-neutral-700 text-neutral-200"
        disabled={disabled}
        onClick={() => {
          if (!capture) {
            return
          }

          createJob({
            delay: 0,
            name: `Capture #${capture.id}`,
            sourceImage: capture.id,
            pipeline: pipelineId,
            projectId: projectId as string,
            startNow: true,
          })
        }}
        size="small"
      >
        <span>{translate(STRING.PROCESS_NOW)}</span>
        {isSuccess ? (
          <CheckIcon className="w-4 h-4 ml-2" />
        ) : isLoading ? (
          <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
        ) : null}
      </Button>
    </BasicTooltip>
  )
}
