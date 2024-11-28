import { Job, JobStatusType, ServerJob, ServerJobStatusCode } from './job'

export type ServerJobDetails = ServerJob & any // TODO: Update this type

export class JobDetails extends Job {
  public constructor(job: ServerJobDetails) {
    super(job)
  }

  get description(): string {
    return `Job ${this.id} "${this.name}"`
  }

  get delay(): number {
    return this._job.delay
  }

  get errors(): string[] {
    return this._job.progress.errors ?? []
  }

  get logs(): string[] {
    return this._job.progress.logs ?? []
  }

  get stages(): {
    details: string
    fields: { key: string; label: string; value?: string | number }[]
    key: string
    name: string
    status: {
      code: ServerJobStatusCode
      label: string
      type: JobStatusType
      color: string
    }
  }[] {
    return this._job.progress.stages.map((stage: any) => {
      const fields: { key: string; label: string; value?: string | number }[] =
        stage.params.map((param: any) => ({
          key: param.key,
          label: param.name,
          value: param.value,
        }))

      return {
        details: stage.status_label,
        fields,
        key: stage.key,
        name: stage.name,
        status: Job.getStatusInfo(stage.status),
      }
    })
  }
}
