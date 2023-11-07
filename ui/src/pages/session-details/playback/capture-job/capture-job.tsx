import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import { CaptureJobDialog } from './capture-job-dialog'
import { ProcessNow } from './process-now'

export const CaptureJob = ({ captureId }: { captureId: string }) => {
  const { capture } = useCaptureDetails(captureId)

  return (
    <>
      <ProcessNow capture={capture} captureId={captureId} />
      {capture?.jobs.length ? (
        <CaptureJobDialog id={capture.jobs[0].id} />
      ) : null}
    </>
  )
}
