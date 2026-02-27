import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { UserPermission } from 'utils/user/types'
import { Pipeline } from './pipeline'

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

export const SERVER_JOB_TYPES = [
  'ml',
  'data_storage_sync',
  'populate_captures_collection',
  'data_export',
  'unknown',
] as const

export type ServerJob = any // TODO: Update this type

export type ServerJobStatusCode = (typeof SERVER_JOB_STATUS_CODES)[number]

export type ServerJobType = (typeof SERVER_JOB_TYPES)[number]

export enum JobStatusType {
  Success,
  Warning,
  Error,
  Neutral,
}

export class Job {
  protected readonly _job: ServerJob

  public constructor(job: ServerJob) {
    this._job = job
  }

  get canCancel(): boolean {
    return (
      this._job.user_permissions.includes(UserPermission.Run) &&
      (this.status.code === 'STARTED' || this.status.code === 'PENDING')
    )
  }

  get canDelete(): boolean {
    return this._job.user_permissions.includes(UserPermission.Delete)
  }

  get canQueue(): boolean {
    return (
      this._job.user_permissions.includes(UserPermission.Run) &&
      this.status.code === 'CREATED'
    )
  }

  get canRetry(): boolean {
    return (
      this._job.user_permissions.includes(UserPermission.Run) &&
      this.status.code !== 'CREATED' &&
      this.status.code !== 'STARTED' &&
      this.status.code !== 'PENDING' &&
      this.status.code !== 'CANCELING'
    )
  }

  get createdAt(): string | undefined {
    if (!this._job.created_at) {
      return
    }

    return getFormatedDateTimeString({ date: new Date(this._job.created_at) })
  }

  get export(): { id: string; format: string } | undefined {
    return this._job.data_export
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

  get progress(): {
    label: string | undefined
    value: number
  } {
    return {
      label: this._job.progress?.summary.status_label,
      value: this._job.progress?.summary.progress ?? 0,
    }
  }
  get project(): string {
    return this._job.project.name
  }

  get type(): {
    key: ServerJobType
    label: string
  } {
    return Job.getJobTypeInfo(this._job.job_type.key)
  }

  get deployment(): { id: string; name: string } | undefined {
    const deployment = this._job.deployment

    return deployment
      ? { id: `${deployment.id}`, name: deployment.name }
      : undefined
  }

  get sourceImage() {
    const capture = this._job.source_image_single

    return capture
      ? {
          id: `${capture.id}`,
          label: `#${capture.id}`,
          sessionId: capture.event_id ? `${capture.event_id}` : undefined,
        }
      : undefined
  }

  get sourceImages(): { id: string; name: string } | undefined {
    const collection = this._job.source_image_collection

    return collection
      ? { id: `${collection.id}`, name: collection.name }
      : undefined
  }

  get status(): {
    code: ServerJobStatusCode
    label: string
    type: JobStatusType
    color: string
  } {
    return Job.getStatusInfo(
      this._job.status ?? this._job.progress.summary.status
    )
  }

  get updatedAt(): string | undefined {
    if (!this._job.updated_at) {
      return
    }

    return getFormatedDateTimeString({ date: new Date(this._job.updated_at) })
  }

  static getJobTypeInfo(key: ServerJobType) {
    const label = {
      ml: 'ML pipeline',
      data_storage_sync: 'Data storage sync',
      populate_captures_collection: 'Populate captures collection',
      data_export: 'Data export',
      unknown: 'Unknown',
    }[key]

    return {
      key,
      label,
    }
  }

  static getStatusInfo(code: ServerJobStatusCode) {
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
