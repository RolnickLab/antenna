import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'

export type ServerJob = any // TODO: Update this type

export enum JobStatus {
  Pending = 'PENDING',
  Started = 'STARTED',
  Success = 'SUCCESS',
  Unknown = 'UNKNOWN',
}

export class Job {
  protected readonly _job: ServerJob

  public constructor(job: ServerJob) {
    this._job = job
  }

  get canDelete(): boolean {
    return this._job.user_permissions.includes(UserPermission.Delete)
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
    return this.getStatus(this._job.status)
  }

  get statusDetails(): string {
    return this._job.progress.summary.status_label
  }

  get statusValue(): number {
    return this._job.progress.summary.progress
  }

  get statusLabel(): string {
    return this.getStatusLabel(this.status)
  }

  protected getStatus(status: string): JobStatus {
    switch (status) {
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

  protected getStatusLabel(status: JobStatus): string {
    switch (status) {
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
