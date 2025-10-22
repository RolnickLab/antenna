import { ServerSpecies, Species } from './species'

export type ServerSpeciesDetails = ServerSpecies & any // TODO: Update this type

interface SummaryData {
  title: string
  data: {
    x: (string | number)[]
    y: number[]
    tickvals?: (string | number)[]
    ticktext?: string[]
  }
  orientation: 'h' | 'v'
  type: any
}
export class SpeciesDetails extends Species {
  public constructor(species: ServerSpeciesDetails) {
    super(species)
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

  get summaryData(): SummaryData[] {
    return this._species.summary_data
  }
}
