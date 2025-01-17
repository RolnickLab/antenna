import { SessionDetails } from 'data-services/models/session-details'
import { TimelineTick } from 'data-services/models/timeline-tick'

export interface ActivityPlotProps {
  session: SessionDetails
  snapToDetections?: boolean
  timeline: TimelineTick[]
  setActiveCaptureId: (captureId: string) => void
}
