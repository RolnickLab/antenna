import { Entity } from './entity'
import { Job } from './job'
import { JobDetails } from './job-details'

export const SERVER_EXPORT_FORMATS = [
  'occurrences_simple_csv',
  'occurrences_simple_json',
] as const

export type ServerExportFormat = (typeof SERVER_EXPORT_FORMATS)[number]

export type ServerExport = any // TODO: Update this type

export class Export extends Entity {
  public readonly job: Job

  public constructor(entity: ServerExport) {
    super(entity)

    this.job = new JobDetails(this._data.job)
  }

  get fileUrl(): string | undefined {
    return this._data.job.result?.file_url
  }

  get typeLabel(): string {
    const key: ServerExportFormat = this._data.format

    return {
      occurrences_simple_csv: 'Occurrences (simple CSV)',
      occurrences_simple_json: 'Occurrences (simple JSON)',
    }[key]
  }
}
