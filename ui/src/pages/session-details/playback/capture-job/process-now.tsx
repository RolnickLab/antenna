import { useCreateJob } from 'data-services/hooks/jobs/useCreateJob'
import { CaptureDetails } from 'data-services/models/capture-details'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

export const ProcessNow = ({
  capture,
  captureId,
}: {
  capture?: CaptureDetails
  captureId: string
}) => {
  const { projectId } = useParams()
  const { createJob, isLoading, isSuccess } = useCreateJob()

  return (
    <Button
      icon={isSuccess ? IconType.RadixCheck : IconType.BatchId}
      disabled={!capture || capture.hasJobInProgress}
      label={translate(STRING.PROCESS_NOW)}
      loading={isLoading}
      theme={ButtonTheme.Neutral}
      onClick={() => {
        createJob({
          delay: 1,
          name: `Capture #${captureId}`,
          sourceImage: captureId,
          projectId: projectId as string,
          startNow: true,
        })
      }}
    />
  )
}
