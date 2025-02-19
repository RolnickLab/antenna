import { Taxon } from './taxa'

export type ServerSpecies = any // TODO: Update this type

export class Species extends Taxon {
  protected readonly _species: ServerSpecies

  public constructor(species: ServerSpecies) {
    super(species)
    this._species = species
  }

  get images(): { src: string }[] {
    return []
  }

  get trainingImagesLabel(): string {
    return 'GBIF'
  }

  get trainingImagesUrl(): string {
    return `https://www.gbif.org/occurrence/gallery?advanced=1&verbatim_scientific_name=${this.name}`
  }
}
