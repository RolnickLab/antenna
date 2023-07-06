export type ServerSpecies = any // TODO: Update this type

export class Species {
  protected readonly _species: ServerSpecies
  private readonly _images: { src: string }[] = []

  public constructor(species: ServerSpecies) {
    this._species = species

    if (species.occurrence_images?.length) {
      this._images = species.occurrence_images.map((image: any) => ({
        src: image,
      }))
    }
  }

  get id(): string {
    return `${this._species.id}`
  }

  get images(): { src: string }[] {
    return this._images
  }

  get name(): string {
    return this._species.name
  }

  get numDetections(): number {
    return this._species.detections_count
  }

  get numOccurrences(): number {
    return this._species.occurrences_count
  }

  get trainingImagesLabel(): string {
    return 'GBIF'
  }

  get trainingImagesUrl(): string {
    return `https://www.gbif.org/occurrence/gallery?advanced=1&verbatim_scientific_name=${this.name}`
  }
}
