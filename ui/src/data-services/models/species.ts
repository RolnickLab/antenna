import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { UserPermission } from 'utils/user/types'
import { Taxon } from './taxa'

export type ServerSpecies = any // TODO: Update this type

export type Tag = { id: number; name: string }

export class Species extends Taxon {
  protected readonly _species: ServerSpecies

  public constructor(species: ServerSpecies) {
    super(species)
    this._species = species
  }

  get adminUrl(): string {
    return `https://api.antenna.insectai.org/bereich/main/taxon/${this.id}` // TODO: Use dynamic admin URL based on environment?
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

  get coverImageCredit(): string | null {
    return this._species.cover_image_credit || null
  }

  get coverImageUrl(): string | null {
    return this._species.cover_image_url || null
  }

  get createdAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._species.created_at),
    })
  }

  get fieldguideId(): string | null {
    return this._species.fieldguide_id || null
  }

  get fieldguideUrl(): string | undefined {
    return this.fieldguideId
      ? `https://leps.fieldguide.ai/categories?category=${this.fieldguideId}`
      : undefined
  }

  get gbifUrl(): string {
    return `https://www.gbif.org/occurrence/gallery?advanced=1&verbatim_scientific_name=${this.name}`
  }

  get iNaturalistId(): string | null {
    return this._species.inat_taxon_id || null
  }

  get iNaturalistUrl(): string | undefined {
    return this.iNaturalistId
      ? `https://www.inaturalist.org/taxa/${this.iNaturalistId}`
      : undefined
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
