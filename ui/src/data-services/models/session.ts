import { getCompactDatespanString } from 'utils/date/getCompactDatespanString/getCompactDatespanString'
import { getCompactTimespanString } from 'utils/date/getCompactTimespanString/getCompactTimespanString'
import { getFormatedDateString } from 'utils/date/getFormatedDateString/getFormatedDateString'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'

export type ServerEvent = any // TODO: Update this type

export class Session {
  protected readonly _event: ServerEvent
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

  get exampleCaptures(): { src: string }[] {
    return this._exampleCaptures
  }

  get id(): string {
    return `${this._event.id}`
  }

  get label(): string {
    return this._event.name
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
