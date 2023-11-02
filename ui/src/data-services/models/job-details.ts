import { Job, ServerJob } from './job'

export type ServerJobDetails = ServerJob & any // TODO: Update this type

export class JobDetails extends Job {
  public constructor(job: ServerJobDetails) {
    super(job)
  }

  get inputLabel(): string {
    return this._job.config.input.name
  }

  get inputValue(): string | number {
    return this._job.config.input.size
  }

  get stages(): { key: string }[] {
    return this._job.config.stages
  }

  get statusDetails(): string {
    return this._job.progress.summary.status_label
  }

  get statusValue(): number {
    return this._job.progress.summary.progress
  }

  getStageInfo(key: string) {
    const stage = this._job.config.stages.find(
      (stage: any) => stage.key === key
    )

    const progress = this._job.progress.stages.find(
      (stage: any) => stage.key === key
    )

    if (!stage || !progress) {
      return undefined
    }

    const name = stage.name
    const status = this.getStatus(progress.status)
    const statusLabel = this.getStatusLabel(status)
    const statusDetails = stage.status_label
    const fields: { key: string; label: string; value?: string | number }[] =
      stage.params.map((param: any) => {
        const configValue = param.value
        const progressValue = progress[param.key]

        return {
          key: param.key,
          label: param.name,
          value: configValue !== undefined ? configValue : progressValue,
        }
      })

    return {
      name,
      status,
      statusLabel,
      statusDetails,
      fields,
    }
  }
}
