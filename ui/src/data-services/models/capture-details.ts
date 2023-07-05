import { Capture, ServerCapture } from './capture'

export type ServerCaptureDetails = ServerCapture & any // TODO: Update this type

export class CaptureDetails extends Capture {
  public constructor(capture: ServerCaptureDetails) {
    super(capture)
  }
}
