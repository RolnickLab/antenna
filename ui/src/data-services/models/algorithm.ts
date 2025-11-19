import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'

export type ServerAlgorithm = any // TODO: Update this type

export class Algorithm {
  protected readonly _algorithm: ServerAlgorithm

  public constructor(algorithm: ServerAlgorithm) {
    this._algorithm = algorithm
  }

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._algorithm.created_at),
    })
  }

  get description(): string | undefined {
    return this._algorithm.description
  }

  get id(): string {
    return `${this._algorithm.id}`
  }

  get name(): string {
    return this._algorithm.name
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

  get updatedAt(): string | undefined {
    if (!this._algorithm.updated_at) {
      return undefined
    }

    return getFormatedDateTimeString({
      date: new Date(this._algorithm.updated_at),
    })
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
}
