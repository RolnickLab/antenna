import { useCreateJob } from 'data-services/hooks/jobs/useCreateJob'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { CaptureDetails } from 'data-services/models/capture-details'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
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
  const { project } = useProjectDetails(projectId as string, true)
  const { createJob, isLoading, isSuccess } = useCreateJob()
  const disabled =
    !capture || capture.hasJobInProgress || !pipelineId || !project?.canUpdate

  // @TODO: hasJobInProgress, replace with if pipeline is healthy/available

  const tooltipContent = project?.canUpdate
    ? translate(STRING.MESSAGE_PROCESS_NOW_TOOLTIP)
    : translate(STRING.MESSAGE_PERMISSIONS_MISSING)

  return (
    <Tooltip content={tooltipContent}>
      <Button
        className="!bg-neutral-700 text-neutral-200"
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
    </Tooltip>
  )
}
