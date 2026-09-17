import { snakeCaseToSentenceCase } from 'utils/snakeCaseToSentenceCase'
import { Entity } from './entity'

export type ServerAlgorithm = any // TODO: Update this type

export interface ServerAlgorithmEvaluation {
  id: number
  occurrence_set: { id: number; name: string }
  accuracy: number | null
  accuracy_by_species: number | null
  occurrences_scored: number
  occurrences_skipped: number
  species_scored: number
  created_at: string
}

export interface AlgorithmEvaluation {
  id: string
  occurrenceSetName: string
  accuracy?: number
  accuracyBySpecies?: number
  occurrencesScored: number
}

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

  get trainable(): boolean {
    return this._algorithm.trainable ?? false
  }

  get evaluations(): AlgorithmEvaluation[] {
    const rows: ServerAlgorithmEvaluation[] = this._algorithm.evaluations ?? []

    return rows.map((row) => ({
      id: `${row.id}`,
      occurrenceSetName: row.occurrence_set.name,
      accuracy: row.accuracy ?? undefined,
      accuracyBySpecies: row.accuracy_by_species ?? undefined,
      occurrencesScored: row.occurrences_scored,
    }))
  }
}
