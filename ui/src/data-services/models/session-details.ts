import { Capture } from './capture'
import { Plot } from './charts'
import { ServerEvent, Session } from './session'

export type ServerEventDetails = ServerEvent & any // TODO: Update this type

export class SessionDetails extends Session {
  private readonly _firstCapture?: Capture

  public constructor(event: ServerEventDetails) {
    super(event)

    if (event.first_capture) {
      this._firstCapture = new Capture(event.first_capture)
    }
  }

  get captureOffset(): number | undefined {
    return this._event.capture_page_offset
  }

  get firstCapture(): Capture | undefined {
    return this._firstCapture
  }

  get detectionsMaxCount() {
    return this._event.stats.detections_max_count
  }

  get detectionsPerCapture():
    | {
        max: number
        median: number
        quartiles: [number, number]
        busiestCaptureId: string
      }
    | undefined {
    const stats = this._event.stats

    if (stats.detections_max_count === null || !stats.busiest_capture) {
      return undefined
    }

    return {
      max: stats.detections_max_count,
      median: stats.detections_median_count,
      quartiles: [stats.detections_q1_count, stats.detections_q3_count],
      busiestCaptureId: `${stats.busiest_capture.id}`,
    }
  }

  get summaryData(): Plot[] {
    return this._event.summary_data
  }
}
