import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import { NewJobDialog } from 'pages/job-details/new-job-dialog'
import { CaptureJobDialog } from './capture-job-dialog'

export const CaptureJob = ({ captureId }: { captureId: string }) => {
  const { capture } = useCaptureDetails(captureId)

  return (
    <>
      <NewJobDialog captureId={captureId} />
      {capture?.jobs.map((job) => (
        <CaptureJobDialog id={job.id} />
      ))}
    </>
  )
}
