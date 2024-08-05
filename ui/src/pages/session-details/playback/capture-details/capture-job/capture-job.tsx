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
    <div style={capture?.jobs.length ? undefined : { gridColumn: 'span 2' }}>
      <ProcessNow capture={capture} pipelineId={pipelineId} />
    </div>
    {capture?.jobs.length ? <CaptureJobDialog id={capture.jobs[0].id} /> : null}
  </>
)
