import { Entity } from './entity'
import { Job } from './job'
import { JobDetails } from './job-details'

export const SERVER_EXPORT_TYPES = [
  'occurrences_simple_csv',
  'occurrences_simple_json',
] as const

export type ServerExportType = (typeof SERVER_EXPORT_TYPES)[number]

export type ServerExport = any // TODO: Update this type

export class Export extends Entity {
  public readonly job: Job
  public readonly sourceImages?: { id: string; name: string }

  public constructor(entity: ServerExport) {
    super(entity)

    this.job = new JobDetails(this._data.job)

    if (this._data.filters.collection && this._data.collection) {
      this.sourceImages = {
        id: this._data.filters.collection,
        name: this._data.collection,
      }
    }
  }

  static getExportTypeInfo(key: ServerExportType) {
    const label = {
      occurrences_simple_csv: 'Occurrences (simple CSV)',
      occurrences_simple_json: 'Occurrences (simple JSON)',
    }[key]

    return {
      key,
      label,
    }
  }

  get fileUrl(): string | undefined {
    return this._data.file_url
  }

  get type(): {
    key: ServerExportType
    label: string
  } {
    return Export.getExportTypeInfo(this._data.format)
  }
}
