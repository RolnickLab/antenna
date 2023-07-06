import { Capture } from './capture'
import { ServerEvent, Session } from './session'

export type ServerEventDetails = ServerEvent & any // TODO: Update this type

export class SessionDetails extends Session {
  private readonly _firstCapture: Capture

  public constructor(event: ServerEventDetails) {
    super(event)

    this._firstCapture = new Capture(event.first_capture)
  }

  get firstCapture(): Capture {
    return this._firstCapture
  }

  get detectionsMaxCount() {
    return this._event.stats.detections_max_count
  }
}
