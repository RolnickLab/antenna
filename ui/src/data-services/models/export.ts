import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'
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

  public constructor(entity: ServerExport) {
    super(entity)

    this.job = new JobDetails(this._data.job)
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

  get fileSizeLabel(): string | undefined {
    return this._data.file_size
  }

  get filtersLabels(): string[] {
    return Object.entries(this._data.filters_display).map(([key, _filter]) => {
      const filter = _filter as { id: number; name: string }

      return `${snakeCaseToSentenceCase(key)}: ${filter.id}`
    })
  }

  get numRecords(): number {
    return this._data.record_count
  }

  get type(): {
    key: ServerExportType
    label: string
  } {
    return Export.getExportTypeInfo(this._data.format)
  }
}
