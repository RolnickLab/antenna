import _ from 'lodash'
import { getCompactDatespanString } from 'utils/getCompactDatespanString'

export type ServerOccurrence = any // TODO: Update this type

export class Occurrence {
  private readonly _occurrence: ServerOccurrence
  private _images: { src: string }[] = []

  public constructor(occurrence: ServerOccurrence) {
    this._occurrence = occurrence
  }

  get categoryLabel(): string {
    return this._occurrence.label
  }

  get categoryScore(): number {
    return _.round(Number(this._occurrence.best_score), 2)
  }

  get deployment(): string {
    return this._occurrence.deployment
  }

  get id(): string {
    return this._occurrence.id
  }

  get images(): { src: string }[] {
    return this._images
  }
  set images(value: { src: string }[]) {
    this._images = value
  }

  get sessionId(): string {
    return this._occurrence.event
  }

  get sessionLabel(): string {
    return `Session ${this.sessionId}`
  }

  get sessionTimespan(): string {
    return getCompactDatespanString({
      date1: new Date(this._occurrence.start_time),
      date2: new Date(this._occurrence.end_time),
    })
  }
}
