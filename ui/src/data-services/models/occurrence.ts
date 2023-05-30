import _ from 'lodash'
import { getCompactDatespanString } from 'utils/getCompactDatespanString/getCompactDatespanString'

export type ServerOccurrence = any // TODO: Update this type

export class Occurrence {
  private readonly _occurrence: ServerOccurrence
  private readonly _images: { src: string }[] = []

  public constructor(occurrence: ServerOccurrence) {
    this._occurrence = occurrence

    this._images = occurrence.examples.map((example: any) => ({
      // TODO: Can we get full URL from API?
      src: `https://api.dev.insectai.org${example.cropped_image_path}`,
    }))
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

  get sessionId(): number {
    return this._occurrence.event.id
  }

  get sessionLabel(): string {
    return `Session ${this._occurrence.event.day}`
  }

  get sessionTimespan(): string {
    return getCompactDatespanString({
      date1: new Date(this._occurrence.start_time),
      date2: new Date(this._occurrence.end_time),
    })
  }
}
