import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'

export type ServerJob = any // TODO: Update this type

export enum JobStatus {
  Pending = 'pending',
  Started = 'started',
  Success = 'success',
  Unknown = 'unknown',
}

export class Job {
  private readonly _job: ServerJob

  public constructor(job: ServerJob) {
    this._job = job
  }

  get finishedAt(): string | undefined {
    if (!this._job.finished_at) {
      return
    }

    const date = new Date(this._job.finished_at)
    const dateString = getFormatedDateString({ date })
    const timeString = getFormatedTimeString({ date })

    return `${dateString} ${timeString}`
  }

  get id(): string {
    return `${this._job.id}`
  }

  get startedAt(): string | undefined {
    if (!this._job.started_at) {
      return
    }

    const date = new Date(this._job.started_at)
    const dateString = getFormatedDateString({ date })
    const timeString = getFormatedTimeString({ date })

    return `${dateString} ${timeString}`
  }

  get name(): string {
    return this._job.name
  }

  get project(): string {
    return this._job.project.name
  }

  get status(): JobStatus {
    switch (this._job.status) {
      case 'PENDING':
        return JobStatus.Pending
      case 'STARTED':
        return JobStatus.Started
      case 'SUCCESS':
        return JobStatus.Success
      default:
        return JobStatus.Unknown
    }
  }

  get statusDetails(): string | undefined {
    return undefined // If we return a string here, it will show up as a tooltip on status bullet hover
  }

  get statusLabel(): string {
    switch (this.status) {
      case JobStatus.Pending:
        return translate(STRING.PENDING)
      case JobStatus.Started:
        return translate(STRING.RUNNING)
      case JobStatus.Success:
        return translate(STRING.DONE)
      default:
        return translate(STRING.UNKNOWN)
    }
  }
}
