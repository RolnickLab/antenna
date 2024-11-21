import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { UserPermission } from 'utils/user/types'
import { Pipeline } from './pipeline'

export type ServerJob = any // TODO: Update this type

export const SERVER_JOB_STATUS_CODES = [
  'CANCELING',
  'CREATED',
  'FAILURE',
  'PENDING',
  'RECEIVED',
  'RETRY',
  'REVOKED',
  'STARTED',
  'SUCCESS',
  'UNKNOWN',
] as const

export type ServerJobStatusCode = (typeof SERVER_JOB_STATUS_CODES)[number]

export enum JobStatusType {
  Error,
  Neutral,
  Success,
  Warning,
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
      (this.status.code === 'STARTED' || this.status.code === 'PENDING')
    )
  }

  get canDelete(): boolean {
    return this._job.user_permissions.includes(UserPermission.Delete)
  }

  get canQueue(): boolean {
    return (
      this._job.user_permissions.includes(UserPermission.Update) &&
      this.status.code === 'CREATED'
    )
  }

  get canRetry(): boolean {
    return (
      this._job.user_permissions.includes(UserPermission.Update) &&
      this.status.code !== 'CREATED' &&
      this.status.code !== 'STARTED' &&
      this.status.code !== 'PENDING'
    )
  }

  get createdAt(): string | undefined {
    if (!this._job.created_at) {
      return
    }

    return getFormatedDateTimeString({ date: new Date(this._job.created_at) })
  }

  get sourceImages(): { id: string; name: string } | undefined {
    const collection = this._job.source_image_collection

    return collection
      ? { id: `${collection.id}`, name: collection.name }
      : undefined
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

  get pipeline(): Pipeline | undefined {
    return this._job.pipeline ? new Pipeline(this._job.pipeline) : undefined
  }

  get project(): string {
    return this._job.project.name
  }

  get jobType(): JobType {
    return this._job.job_type
  }

  get deployment(): { id: string; name: string } | undefined {
    const deployment = this._job.deployment

    return deployment
      ? { id: `${deployment.id}`, name: deployment.name }
      : undefined
  }

  get status(): {
    code: ServerJobStatusCode
    label: string
    type: JobStatusType
    color: string
  } {
    return this.getStatusInfo(this._job.status)
  }

  get progress(): {
    label: string | undefined
    value: number
  } {
    return {
      label: this._job.progress?.summary.status_label,
      value: this._job.progress?.summary.progress ?? 0,
    }
  }

  get updatedAt(): string | undefined {
    if (!this._job.updated_at) {
      return
    }

    return getFormatedDateTimeString({ date: new Date(this._job.updated_at) })
  }

  protected getStatusInfo(code: ServerJobStatusCode) {
    const label =
      String(code).charAt(0).toUpperCase() + String(code).toLowerCase().slice(1)

    const type = {
      CANCELING: JobStatusType.Warning,
      CREATED: JobStatusType.Neutral,
      FAILURE: JobStatusType.Error,
      PENDING: JobStatusType.Warning,
      RECEIVED: JobStatusType.Neutral,
      RETRY: JobStatusType.Warning,
      REVOKED: JobStatusType.Error,
      STARTED: JobStatusType.Warning,
      SUCCESS: JobStatusType.Success,
      UNKNOWN: JobStatusType.Neutral,
    }[code]

    const color = {
      [JobStatusType.Error]: '#ef4444', // color-destructive-500,
      [JobStatusType.Neutral]: '#78777f', // color-neutral-300
      [JobStatusType.Success]: '#09af8a', // color-success-500
      [JobStatusType.Warning]: '#f59e0b', // color-warning-500
    }[type]

    return {
      code,
      label,
      type,
      color,
    }
  }
}
