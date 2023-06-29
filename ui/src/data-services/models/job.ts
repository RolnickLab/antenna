import { getFormatedDateString } from 'utils/date/getFormatedDateString/getCompactDatespanString'
import { STRING, translate } from 'utils/language'

export type ServerJob = any // TODO: Update this type

export class Job {
  private readonly _job: ServerJob

  public constructor(job: ServerJob) {
    this._job = job
  }

  get description(): string {
    return this._job.description
  }

  get id(): string {
    return this._job.id
  }

  get idLabel(): string {
    return `#${this.id}`
  }

  get jobStarted(): string {
    return getFormatedDateString({ date: new Date(this._job.job_started) })
  }

  get project(): string {
    return this._job.project
  }

  get totalImages(): number {
    return this._job.total_images
  }

  get status(): number {
    return this._job.status
  }

  get statusDetails(): string {
    return 'More details about the job status.'
  }

  get statusLabel(): string {
    switch (this._job.status) {
      case 0:
        return translate(STRING.RUNNING)
      case 1:
        return translate(STRING.STOPPED)
      case 2:
        return translate(STRING.DONE)
      default:
        return translate(STRING.UNKNOWN)
    }
  }
}
