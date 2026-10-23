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

  get summaryData(): Plot[] {
    return this._event.summary_data
  }
}
