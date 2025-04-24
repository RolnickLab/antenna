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

  get coverImage() {
    // TODO: Replace dummy data
    return {
      url: 'http://production-chroma.s3.amazonaws.com/photos/61883e24fe9c0e7e7bf2fa31/4b747bb37e644f8bbc71ef392ab2ee82.jpg',
      copyright: 'Josh Vandermeulen, some rights reserved (CC BY-NC-ND)',
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

  get gbifUrl(): string {
    return `https://www.gbif.org/occurrence/gallery?advanced=1&verbatim_scientific_name=${this.name}`
  }

  get score(): number {
    return this._species.best_determination_score || 0
  }

  get scoreLabel(): string {
    return this.score.toFixed(2)
  }
}
