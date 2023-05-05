export type ServerSpecies = any // TODO: Update this type

export class Species {
  private readonly _species: ServerSpecies
  private readonly _images: { src: string }[] = []

  public constructor(species: ServerSpecies) {
    this._species = species

    this._images = species.examples.map((example: any) => ({
      // TODO: Can we get full URL from API?
      src: `https://api.dev.insectai.org${example.cropped_image_path}`,
    }))
  }

  get id(): string {
    return this._species.name // TODO: Update when BE is returning an ID
  }

  get images(): { src: string }[] {
    return this._images
  }

  get name(): string {
    return this._species.name
  }

  get numDetections(): number {
    return this._species.num_detections
  }

  get numOccurrences(): number {
    return this._species.num_occurrences
  }
}
