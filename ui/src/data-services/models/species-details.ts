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

  get summaryData(): Plot[] {
    return this._species.summary_data
  }
}
