import { useCreateJob } from 'data-services/hooks/jobs/useCreateJob'
import { CaptureDetails } from 'data-services/models/capture-details'
import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'

export const ProcessNow = ({
  capture,
  pipelineId,
}: {
  capture: CaptureDetails
  pipelineId?: string
}) => {
  const { projectId } = useParams()
  const { createJob, isLoading, isSuccess } = useCreateJob()
  const canProcess = capture.userPermissions.includes(
    UserPermission.RunSingleImage
  )
  const disabled =
    isLoading || capture.hasJobInProgress || !pipelineId || !canProcess
  // @TODO: also check if pipeline is healthy/available

  return (
    <Button
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
      variant="success"
    >
      <span>{translate(STRING.PROCESS_NOW)}</span>
      {isSuccess ? (
        <CheckIcon className="w-4 h-4 ml-2" />
      ) : isLoading ? (
        <Loader2Icon className="w-4 h-4 ml-2 animate-spin" />
      ) : null}
    </Button>
  )
}
