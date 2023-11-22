import { Capture, ServerCapture } from './capture'
import { Job, JobStatus } from './job'

export type ServerCaptureDetails = ServerCapture & any // TODO: Update this type

export class CaptureDetails extends Capture {
  private readonly _jobs: Job[] = []

  public constructor(capture: ServerCaptureDetails) {
    super(capture)

    if (this._capture.jobs) {
      this._jobs = this._capture.jobs.map((job: any) => new Job(job))
    }
  }

  get hasJobInProgress(): boolean {
    return this._jobs.some(
      (job) =>
        job.status === JobStatus.Created ||
        job.status === JobStatus.Pending ||
        job.status === JobStatus.Started
    )
  }

  get jobs(): Job[] {
    return this._jobs
  }

  get sizeLabel(): string {
    return `${this._capture.size} B`
  }

  get url(): string {
    return this._capture.url
  }
}
