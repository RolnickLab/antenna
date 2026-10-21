import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'
import { Entity } from './entity'
import { Job } from './job'
import { JobDetails } from './job-details'

export const SERVER_EXPORT_TYPES = [
  'occurrences_simple_csv',
  'occurrences_api_json',
] as const

export type ServerExportType = (typeof SERVER_EXPORT_TYPES)[number]

export type ServerExport = any // TODO: Update this type

// A filter on a related object is shown by name, for example a capture set.
type ServerFilterDisplayValue =
  | { id: number | string; name: string }
  | string
  | number
  | null

export class Export extends Entity {
  public readonly job?: Job

  public constructor(entity: ServerExport) {
    super(entity)

    if (this._data.job) {
      this.job = new JobDetails(this._data.job)
    }
  }

  static getExportTypeInfo(key: ServerExportType) {
    const label = {
      occurrences_simple_csv: 'Occurrences (simple CSV)',
      occurrences_api_json: 'Occurrences (API JSON)',
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
    return this._data.file_size_display
  }
  get filtersLabels(): string[] {
    const filtersObj: { [key: string]: ServerFilterDisplayValue } =
      this._data.filters_display || this._data.filters || {}

    return Object.entries(filtersObj).map(([_key, _value]) => {
      const value =
        _value !== null && typeof _value === 'object' ? _value.name : _value
      const key = _key.replace('collection', 'capture set') // TODO: Temporary fix until backend terminology is updated

      return `${snakeCaseToSentenceCase(key)}: ${value}`
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
