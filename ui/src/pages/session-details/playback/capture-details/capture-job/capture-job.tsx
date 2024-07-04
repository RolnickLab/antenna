import { CaptureDetails } from 'data-services/models/capture-details'
import { CaptureJobDialog } from './capture-job-dialog'
import { ProcessNow } from './process-now'

export const CaptureJob = ({
  capture,
  pipelineId,
}: {
  capture?: CaptureDetails
  pipelineId?: string
}) => (
  <>
    <ProcessNow capture={capture} pipelineId={pipelineId} />
    {capture?.jobs.length ? <CaptureJobDialog id={capture.jobs[0].id} /> : null}
  </>
)
