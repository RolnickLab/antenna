import { getCompactDatespanString } from 'utils/getCompactDatespanString'
import { getCompactTimespanString } from 'utils/getCompactTimespanString'

export type ServerEvent = any // TODO: Update this type

export class Session {
  private readonly _event: ServerEvent

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
    return `#${this._event.id}`
  }

  get images(): { src: string }[] {
    return [
      {
        src: 'https://placekitten.com/240/240',
      },
      {
        src: 'https://placekitten.com/240/160',
      },
      {
        src: 'https://placekitten.com/160/240',
      },
    ]
  }

  get numDetections(): number {
    return this._event.num_detections
  }

  get numImages(): number {
    return this._event.num_source_images
  }

  get timespanLabel(): string {
    return getCompactTimespanString({
      date1: new Date(this._event.start_time),
      date2: new Date(this._event.end_time),
    })
  }

  get timestamp(): Date {
    return new Date(this._event.start_time)
  }
}
