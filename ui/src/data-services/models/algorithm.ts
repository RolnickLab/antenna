import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'
import { Entity } from './entity'

export type ServerAlgorithm = any // TODO: Update this type

export class Algorithm extends Entity {
  protected readonly _algorithm: ServerAlgorithm

  public constructor(algorithm: ServerAlgorithm) {
    super(algorithm)

    this._algorithm = algorithm
  }

  get key(): string {
    return this._algorithm.key
  }

  get version(): string {
    return this._algorithm.version
  }

  get uri(): string {
    return this._algorithm.uri
  }

  get taskType(): string {
    return snakeCaseToSentenceCase(this._algorithm.task_type)
  }

  get categoryMapURI(): string {
    return this._algorithm.category_map
      ? this._algorithm.category_map.details
      : ''
  }

  get categoryMapID(): string {
    return this._algorithm.category_map ? this._algorithm.category_map.id : ''
  }

  get categoryCount(): number | undefined {
    return this._algorithm.category_count
      ? this._algorithm.category_count
      : undefined
  }

  // Whether the algorithm is on a pipeline the active project has enabled. The
  // project list also includes algorithms that only ran historically (superseded
  // versions, post-processing algorithms), which come back false so the UI can gray
  // them out. Undefined on the unscoped list, where there is no project to be enabled in.
  get enabledInProject(): boolean | undefined {
    return this._algorithm.enabled_in_project ?? undefined
  }
}
