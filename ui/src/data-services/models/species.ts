export type ServerSpecies = any // TODO: Update this type

export class Species {
  private readonly _species: ServerSpecies
  private readonly _images: { src: string }[] = []

  public constructor(species: ServerSpecies) {
    this._species = species

    if (species.latest_detection) {
      this._images = [{ src: species.latest_detection?.url }]
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
}
