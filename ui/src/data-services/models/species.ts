import { UserPermission } from 'utils/user/types'
import { Taxon } from './taxa'

export type ServerSpecies = any // TODO: Update this type

export class Species extends Taxon {
  protected readonly _species: ServerSpecies

  public constructor(species: ServerSpecies) {
    super(species)
    this._species = species
  }

  get userPermissions(): UserPermission[] {
    return this._species.user_permissions
  }

  get coverImage() {
    if (!this._species.cover_image_url) {
      return undefined
    }

    if (!this._species.cover_image_credit) {
      return {
        url: this._species.cover_image_url,
        caption: this.name,
      }
    }

    return {
      url: this._species.cover_image_url,
      caption: this.name,
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

  get score(): number {
    return this._species.best_determination_score || 0
  }

  get scoreLabel(): string {
    return this.score.toFixed(2)
  }

  get tags() {
    /* TODO: Replace dummy data */
    return [
      ...(this.isUnknown
        ? [
            {
              label: 'Unknown species',
              value: 'unknown-species',
            },
          ]
        : []),
    ]
  }
}
