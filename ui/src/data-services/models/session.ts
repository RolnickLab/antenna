import { getCompactDatespanString } from 'utils/getCompactDatespanString'
import { getCompactTimespanString } from 'utils/getCompactTimespanString'

export type ServerEvent = any // TODO: Update this type

export class Session {
  private readonly _event: ServerEvent
  private _images: { src: string }[] = []

  public constructor(event: ServerEvent) {
    this._event = event
  }

  get datespanLabel(): string {
    return getCompactDatespanString({
      date1: new Date(this._event.start_time),
      date2: new Date(this._event.end_time),
    })
  }

  get deploymentLabel(): string {
    return this._event.deployment
  }

  get durationLabel(): string {
    return this._event.duration_label
  }

  get durationMinutes(): number {
    return this._event.duration_minutes
  }

  get id(): string {
    return `${this._event.id}`
  }

  get idLabel(): string {
    return `#${this.id}`
  }

  get images(): { src: string }[] {
    return this._images
  }
  set images(value: { src: string }[]) {
    this._images = value
  }

  get numDetections(): number {
    return this._event.num_detections
  }

  get numImages(): number {
    return this._event.num_source_images
  }

  get numOccurrences(): number {
    return this._event.num_occurrences
  }

  get numSpecies(): number {
    return this._event.num_species
  }

  get timespanLabel(): string {
    return getCompactTimespanString({
      date1: new Date(this._event.start_time),
      date2: new Date(this._event.end_time),
    })
  }
}
