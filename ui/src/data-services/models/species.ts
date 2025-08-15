import { getFormatedDateTimeString } from 'utils/date/getFormatedDateTimeString/getFormatedDateTimeString'
import { Taxon } from './taxa'

export type ServerSpecies = any // TODO: Update this type

export class Species extends Taxon {
  protected readonly _species: ServerSpecies

  public constructor(species: ServerSpecies) {
    super(species)
    this._species = species
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

  get updatedAt(): string {
    return getFormatedDateTimeString({
      date: new Date(this._species.updated_at),
    })
  }
}
