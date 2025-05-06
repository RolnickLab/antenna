import { Capture, ServerCapture } from './capture'
import { Job } from './job'

export type ServerCaptureDetails = ServerCapture & any // TODO: Update this type

export class CaptureDetails extends Capture {
  private readonly _jobs: Job[] = []

  public constructor(capture: ServerCaptureDetails) {
    super(capture)

    if (this._capture.jobs) {
      this._jobs = this._capture.jobs.map((job: any) => new Job(job))
    }
  }

  get currentIndex(): number | undefined {
    return this._capture.event_current_capture_index
  }

  get currentJob(): Job | undefined {
    if (!this._jobs.length) {
      return
    }

    return this._jobs.sort((j1: Job, j2: Job) => {
      const date1 = new Date(j1.updatedAt as string)
      const date2 = new Date(j2.updatedAt as string)

      return date2.getTime() - date1.getTime()
    })[0]
  }

  get hasJobInProgress(): boolean {
    return this._jobs.some(
      (job) =>
        job.status.code === 'CREATED' ||
        job.status.code === 'PENDING' ||
        job.status.code === 'STARTED'
    )
  }

  get isStarred(): boolean {
    return this._capture.collections?.some(
      (collection: any) => collection.method === 'starred'
    )
  }

  get jobs(): Job[] {
    return this._jobs
  }

  get nextCaptureId(): string | undefined {
    return this._capture.event_next_capture_id
  }

  get prevCaptureId(): string | undefined {
    return this._capture.event_prev_capture_id
  }

  get sizeLabel(): string {
    return `${this._capture.size_display}`
  }

  get totalCaptures(): number | undefined {
    return this._capture.event_total_captures
  }

  get url(): string {
    return this._capture.url
  }
}
