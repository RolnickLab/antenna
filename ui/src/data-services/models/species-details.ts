import { Plot } from './charts'
import { ServerSpecies, Species } from './species'

export type ServerSpeciesDetails = ServerSpecies & any // TODO: Update this type

export interface ServerAlgorithmPerformance {
  algorithm: { id: number; name: string; key: string; version: number }
  occurrence_set: { id: number; name: string }
  accuracy: number
  occurrences_scored: number
  correct: number
  overall_accuracy: number | null
  overall_accuracy_by_species: number | null
}

export interface AlgorithmPerformance {
  algorithmId: string
  algorithmName: string
  accuracy: number
  occurrencesScored: number
  correct: number
  occurrenceSetName: string
}

export class SpeciesDetails extends Species {
  public constructor(species: ServerSpeciesDetails) {
    super(species)
  }

  get algorithmPerformance(): AlgorithmPerformance[] {
    const rows = this._species.algorithm_performance ?? []

    return rows.map((row: ServerAlgorithmPerformance) => ({
      algorithmId: `${row.algorithm.id}`,
      algorithmName: row.algorithm.name,
      accuracy: row.accuracy,
      occurrencesScored: row.occurrences_scored,
      correct: row.correct,
      occurrenceSetName: row.occurrence_set.name,
    }))
  }

  get commonNameLabel(): string | undefined {
    return this._species.common_name_en ?? undefined
  }

  get exampleOccurrence() {
    const occurrence = this._species.occurrences?.[0]

    if (!occurrence?.best_detection) {
      return undefined
    }

    return {
      id: occurrence.id,
      url: occurrence.best_detection.url,
      caption: undefined,
    }
  }

  get summaryData(): Plot[] {
    return this._species.summary_data
  }
}
