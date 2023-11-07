import { Job, JobStatus, ServerJob } from './job'
import { Pipeline } from './pipeline'

export type ServerJobDetails = ServerJob & any // TODO: Update this type

export class JobDetails extends Job {
  public constructor(job: ServerJobDetails) {
    super(job)
  }

  get delay(): number {
    return this._job.delay
  }

  get pipeline(): Pipeline | undefined {
    return this._job.pipeline ? new Pipeline(this._job.pipeline) : undefined
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

      return {
        fields: [], // TODO: Update
        key: stage.key,
        name: stage.name,
        status,
        statusLabel: this.getStatusLabel(status),
        statusDetails: stage.status_label,
      }
    })
  }

  get sourceImages(): { id: string; name: string } | undefined {
    const collection = this._job.source_image_collection

    return collection
      ? { id: `${collection.id}`, name: collection.name }
      : undefined
  }

  get sourceImage(): { id: string } | undefined {
    const capture = this._job.source_image_single

    return capture ? { id: `${capture.id}` } : undefined
  }

  get statusDetails(): string {
    return this._job.progress.summary.status_label
  }

  get statusValue(): number {
    return this._job.progress.summary.progress
  }
}
