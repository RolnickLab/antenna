import { UserPermission } from 'utils/user/types'
import { Taxon } from './taxa'

export type ServerSpecies = any // TODO: Update this type

export type Tag = { id: number; name: string }

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

  get isUnknown(): boolean {
    return this._species.unknown_species
  }

  get lastSeenLabel() {
    if (!this._species.last_detected) {
      return undefined
    }

    const date = new Date(this._species.last_detected)

    return `${date.toLocaleDateString()} ${date.toLocaleTimeString()}`
  }

  get numDetections(): number {
    return this._species.detections_count ?? 0
  }

  get numOccurrences(): number {
    return this._species.occurrences_count ?? 0
  }

  get gbifUrl(): string {
    return `https://www.gbif.org/occurrence/gallery?advanced=1&verbatim_scientific_name=${this.name}`
  }

  get fieldguideUrl(): string | undefined {
    if (!this._species.fieldguide_id) {
      return undefined
    }

    return `https://leps.fieldguide.ai/categories?category=${this._species.fieldguide_id}`
  }

  get images(): {
    [key: string]: {
      caption: string | null
      sizes: { original: string | null }
      title: string
    }
  } {
    return this._species.images
  }

  get score(): number {
    return this._species.best_determination_score || 0
  }

  get scoreLabel(): string {
    return this.score.toFixed(2)
  }

  get thumbnailUrl() {
    if (!this._species.images) {
      return undefined
    }

    const getImageUrl = (key: string): string | undefined =>
      this._species.images[key]?.sizes?.original

    return (
      getImageUrl('external_reference') ??
      getImageUrl('most_recently_featured') ??
      getImageUrl('highest_determination_score')
    )
  }

  get tags(): Tag[] {
    const tags = this._species.tags ?? []

    return tags.sort((t1: Tag, t2: Tag) => t1.id - t2.id)
  }

  get userPermissions(): UserPermission[] {
    return this._species.user_permissions
  }
}
