import _ from 'lodash'
import { ServerSpecies, Species } from './species'

export type ServerSpeciesDetails = ServerSpecies & any // TODO: Update this type

export class SpeciesDetails extends Species {
  public constructor(species: ServerSpeciesDetails) {
    super(species)
  }

  get exampleOccurrence() {
    const occurrence = this._species.occurrences?.[0]

    if (!occurrence?.best_detection) {
      return
    }

    return {
      id: occurrence.id,
      image_url: occurrence.best_detection.url,
      caption: `${occurrence.event.name}\n${
        occurrence.determination.name
      } (${_.round(occurrence.determination_score, 4)})`,
    }
  }

  get fieldguideUrl() {
    return 'https://leps.fieldguide.ai/figures?category=59bafb78929d3d10ea903ee9'
  }
}
