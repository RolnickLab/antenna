import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'

export type ServerJob = any // TODO: Update this type

export enum JobStatus {
  Created = 'created',
  Pending = 'pending',
  Started = 'started',
  Success = 'success',
  Canceling = 'canceling',
  Revoked = 'revoked',
  Failed = 'failed',
  Unknown = 'unknown',
}

export type JobType = {
  name: string
  key: string
}

export class Job {
  protected readonly _job: ServerJob

  public constructor(job: ServerJob) {
    this._job = job
  }

  get canCancel(): boolean {
    return (
      this._job.user_permissions.includes(UserPermission.Update) &&
      this.status === JobStatus.Started
    )
  }

  get canDelete(): boolean {
    return this._job.user_permissions.includes(UserPermission.Delete)
  }

  get canQueue(): boolean {
    return (
      this._job.user_permissions.includes(UserPermission.Update) &&
      this.status === JobStatus.Created
    )
  }

  get createdAt(): string | undefined {
    if (!this._job.created_at) {
      return
    }

    return getFormatedDateTimeString({ date: new Date(this._job.created_at) })
  }

  get finishedAt(): string | undefined {
    if (!this._job.finished_at) {
      return
    }

    return getFormatedDateTimeString({ date: new Date(this._job.finished_at) })
  }

  get id(): string {
    return `${this._job.id}`
  }

  get startedAt(): string | undefined {
    if (!this._job.started_at) {
      return
    }

    return getFormatedDateTimeString({ date: new Date(this._job.started_at) })
  }

  get name(): string {
    return this._job.name
  }

  get project(): string {
    return this._job.project.name
  }

  get jobType(): JobType {
    return this._job.job_type
  }

  get status(): JobStatus {
    return this.getStatus(this._job.status)
  }

  get statusDetails(): string {
    return this._job.progress?.summary.status_label
  }

  get statusValue(): number {
    return this._job.progress?.summary.progress ?? this._job.status
  }

  get statusLabel(): string {
    return this.getStatusLabel(this.status)
  }

  protected getStatus(status: string): JobStatus {
    switch (status) {
      case 'CREATED':
        return JobStatus.Created
      case 'PENDING':
        return JobStatus.Pending
      case 'STARTED':
        return JobStatus.Started
      case 'SUCCESS':
        return JobStatus.Success
      case 'CANCELING':
        return JobStatus.Canceling
      case 'REVOKED':
        return JobStatus.Revoked
      case 'FAILURE':
        return JobStatus.Failed
      default:
        return JobStatus.Unknown
    }
  }

  protected getStatusLabel(status: JobStatus): string {
    switch (status) {
      case JobStatus.Created:
        return translate(STRING.CREATED)
      case JobStatus.Pending:
        return translate(STRING.PENDING)
      case JobStatus.Started:
        return translate(STRING.RUNNING)
      case JobStatus.Success:
        return translate(STRING.DONE)
      case JobStatus.Canceling:
        return translate(STRING.CANCELING)
      case JobStatus.Revoked:
        return translate(STRING.REVOKED)
      case JobStatus.Failed:
        return translate(STRING.FAILED)
      default:
        return translate(STRING.UNKNOWN)
    }
  }
}
