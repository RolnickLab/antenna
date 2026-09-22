import { Plot } from './charts'
import { ServerSpecies, Species } from './species'

export type ServerSpeciesDetails = ServerSpecies & any // TODO: Update this type

export class SpeciesDetails extends Species {
  public constructor(species: ServerSpeciesDetails) {
    super(species)
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

  // The classifiers that can return this species, so a user can tell a taxon a
  // model could predict from one that can only be identified by hand.
  get predictedByAlgorithms(): { id: string; name: string }[] {
    return (this._species.predicted_by_algorithms ?? []).map(
      (algorithm: { id: number | string; name: string }) => ({
        id: `${algorithm.id}`,
        name: algorithm.name,
      })
    )
  }

  get summaryData(): Plot[] {
    return this._species.summary_data
  }
}
