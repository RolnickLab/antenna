import { Job, JobStatus, ServerJob } from './job'

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
    fields: { key: string; label: string; value?: string | number }[]
    name: string
    key: string
    status: JobStatus
    statusLabel: string
    statusDetails: string
  }[] {
    return this._job.progress.stages.map((stage: any) => {
      const status = this.getStatus(stage.status)

      const fields: { key: string; label: string; value?: string | number }[] =
        stage.params.map((param: any) => ({
          key: param.key,
          label: param.name,
          value: param.value,
        }))

      return {
        fields,
        key: stage.key,
        name: stage.name,
        status,
        statusLabel: this.getStatusLabel(status),
        statusDetails: stage.status_label,
      }
    })
  }

  get sourceImage() {
    const capture = this._job.source_image_single

    return capture
      ? {
          id: `${capture.id}`,
          label: `${capture.id}`,
          sessionId: capture.event_id ? `${capture.event_id}` : undefined,
        }
      : undefined
  }
}
