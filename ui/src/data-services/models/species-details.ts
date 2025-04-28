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
      caption: `${occurrence.determination.name} (${_.round(
        occurrence.determination_score,
        4
      )}), ${occurrence.event.name}`,
    }
  }

  get stationsLabel() {
    // TODO: Replace dummy data
    return 'AMI 2BD0E9C1, AMI BEF510C3, AMI E43B615A'
  }

  get fieldguideUrl() {
    // TODO: Replace dummy data
    return 'https://leps.fieldguide.ai/figures?category=59bafb78929d3d10ea903ee9'
  }
}
