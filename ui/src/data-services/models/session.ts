import { getCompactDatespanString } from 'utils/date/getCompactDatespanString/getCompactDatespanString'
import { getCompactTimespanString } from 'utils/date/getCompactTimespanString/getCompactTimespanString'
import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'

export type ServerEvent = any // TODO: Update this type

export class Session {
  private readonly _event: ServerEvent
  private readonly _exampleCaptures: { src: string }[] = []

  public constructor(event: ServerEvent) {
    this._event = event

    if (event.example_captures?.length) {
      this._exampleCaptures = event.example_captures?.map((capture: any) => ({
        src: capture.url,
      }))
    }
  }

  get datespanLabel(): string {
    if (!this._event.end) {
      return getFormatedDateString({ date: new Date(this._event.start) })
    }

    return getCompactDatespanString({
      date1: new Date(this._event.start),
      date2: new Date(this._event.end),
    })
  }

  get deploymentLabel(): string {
    return this._event.deployment.name
  }

  get deploymentId(): string {
    return `${this._event.deployment.id}`
  }

  get durationLabel(): string {
    return this._event.duration_label
  }

  get durationMinutes(): number {
    return this._event.duration_minutes
  }

  get exampleCaptures(): { src: string }[] {
    return this._exampleCaptures
  }

  get id(): string {
    return `${this._event.id}`
  }

  get idLabel(): string {
    return `Session #${this.id}`
  }

  get numDetections(): number | undefined {
    return this._event.detections_count
  }

  get numImages(): number | undefined {
    return this._event.captures_count
  }

  get numOccurrences(): number | undefined {
    return this._event.occurrences_count
  }

  get numSpecies(): number | undefined {
    return this._event.taxa_count
  }

  get tempLabel(): string | undefined {
    return undefined
  }

  get timespanLabel(): string {
    if (!this._event.end) {
      return getFormatedTimeString({ date: new Date(this._event.start) })
    }

    return getCompactTimespanString({
      date1: new Date(this._event.start),
      date2: new Date(this._event.end),
    })
  }
}
