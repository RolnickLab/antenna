import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'
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
    return this.canUpdate && this._data.method !== 'starred'
  }

  get method(): string {
    return this._data.method
  }

  get kwargs(): object {
    return this._data.kwargs || {}
  }

  get methodNameDisplay(): string {
    return snakeCaseToSentenceCase(this._data.method)
  }

  get methodDetailsDisplay(): string[] {
    return Object.entries(this._data.kwargs).map(
      ([key, value]) => `${snakeCaseToSentenceCase(key)} ${value}`
    )
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
}
