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

  get trainable(): boolean {
    return !!this._algorithm.trainable
  }

  /** Settings a retrain would use, which the training job form starts from. */
  get trainingConfig(): {
    min_per_species?: number
    test_fraction?: number
  } {
    return this._algorithm.training_config ?? {}
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
