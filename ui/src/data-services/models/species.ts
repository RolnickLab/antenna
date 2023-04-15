export type ServerEvent = any // TODO: Update this type

export class Species {
  private readonly _species: ServerEvent
  private readonly _images: { src: string }[] = []

  public constructor(species: ServerEvent) {
    this._species = species

    this._images = species.examples.map((example: any) => ({
      // TODO: Can we get full URL from API?
      src: `https://api.dev.insectai.org${example.cropped_image_path}`,
    }))
  }

  get id(): string {
    return this._species.id
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
