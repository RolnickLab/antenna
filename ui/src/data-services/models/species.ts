import { Taxon } from './taxa'

export type ServerSpecies = any // TODO: Update this type

export class Species extends Taxon {
  protected readonly _species: ServerSpecies
  private readonly _images: { src: string }[] = []

  public constructor(species: ServerSpecies) {
    super(species)
    this._species = species

    if (species.occurrence_images?.length) {
      this._images = species.occurrence_images.map((image: any) => ({
        src: image,
      }))
    }
  }

  get images(): { src: string }[] {
    return this._images
  }

  get numDetections(): number {
    return this._species.detections_count || null
  }

  get numOccurrences(): number {
    return this._species.occurrences_count || null
  }

  get trainingImagesLabel(): string {
    return 'GBIF'
  }

  get trainingImagesUrl(): string {
    return `https://www.gbif.org/occurrence/gallery?advanced=1&verbatim_scientific_name=${this.name}`
  }

  get score(): number {
    return this._species.best_determination_score
  }

  get scoreLabel(): string {
    return this.score.toFixed(2)
  }
}
