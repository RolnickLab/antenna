import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
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

  get coverImage(): { url: string; caption?: string } | undefined {
    if (!this._species.cover_image_url) {
      return undefined
    }

    return {
      url: this._species.cover_image_url,
      caption: this._species.cover_image_credit ?? undefined,
    }
  }

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._species.created_at),
    })
  }

  get djangoAdminUrl(): string {
    // TODO: Replace hard coded URL when available from API
    return `https://api-ood.antenna.insectai.org/admin/main/taxon/${this._species.id}/`
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

  get score(): number | undefined {
    const score = this._species.best_determination_score

    if (score || score === 0) {
      return score
    }

    return undefined
  }

  get scoreLabel(): string | undefined {
    if (this.score !== undefined) {
      return this.score.toFixed(2)
    }

    return undefined
  }

  get tags(): Tag[] {
    const tags = this._species.tags ?? []

    return tags.sort((t1: Tag, t2: Tag) => t1.id - t2.id)
  }

  get updatedAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._species.updated_at),
    })
  }

  get userPermissions(): UserPermission[] {
    return this._species.user_permissions
  }
}
