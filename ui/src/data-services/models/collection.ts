import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'
import { UserPermission } from 'utils/user/types'
import { Entity } from './entity'
import { Job } from './job'

export type ServerCollection = any // TODO: Update this type

export class Collection extends Entity {
  private readonly _jobs: Job[] = []

  public constructor(entity: ServerCollection) {
    super(entity)

    if (this._data.jobs) {
      this._jobs = this._data.jobs.map((job: any) => new Job(job))
    }
  }

  get canPopulate(): boolean {
    return (
      this._data.user_permissions.includes(UserPermission.Populate) &&
      this._data.method !== 'starred'
    )
  }

  get currentJob(): Job | undefined {
    if (!this._jobs.length) {
      return
    }

    return this._jobs.sort((j1: Job, j2: Job) => {
      const date1 = new Date(j1.updatedAt as string)
      const date2 = new Date(j2.updatedAt as string)

      return date2.getTime() - date1.getTime()
    })[0]
  }

  get kwargs(): { [key: string]: string | number } {
    return this._data.kwargs || {}
  }

  get method(): string {
    return this._data.method
  }

  get name(): string {
    return this._data.name
  }

  get numImages(): number | undefined {
    return this._data.source_images_count
  }

  get numImagesWithDetections(): number | undefined {
    return this._data.source_images_with_detections_count
  }

  get numImagesWithDetectionsLabel(): string {
    const pct =
      this.numImagesWithDetections && this.numImages
        ? (this.numImagesWithDetections / this.numImages) * 100
        : 0
    return `${this.numImagesWithDetections?.toLocaleString()} / ${this.numImages?.toLocaleString()} (${pct.toFixed(
      0
    )}%)`
  }

  get numJobs(): number | undefined {
    return this._data.jobs?.length
  }

  get numOccurrences(): number {
    return this._data.occurrences_count
  }

  get numTaxa(): number {
    return this._data.taxa_count
  }

  get settingsDisplay(): string {
    if (this.method === 'common_combined') {
      return snakeCaseToSentenceCase(this.type)
    }

    return snakeCaseToSentenceCase(this.method)
  }

  get settingsDetailsDisplay(): string[] {
    return Object.entries(this._data.kwargs).map(
      ([key, value]) => `${snakeCaseToSentenceCase(key)}: ${value}`
    )
  }

  get type(): string {
    if (this.kwargs['max_num'] !== undefined) {
      return 'random_sample'
    }

    if (this.kwargs['minute_interval'] !== undefined) {
      return 'interval_sample'
    }

    return 'full_sample'
  }
}
