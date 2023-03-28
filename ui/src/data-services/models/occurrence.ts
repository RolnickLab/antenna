import _ from 'lodash'
import { getCompactDatespanString } from 'utils/getCompactDatespanString'

export type ServerOccurrence = any // TODO: Update this type

export class Occurrence {
  private readonly _occurrence: ServerOccurrence

  public constructor(occurrence: ServerOccurrence) {
    this._occurrence = occurrence
  }

  get appearanceDuration(): string {
    return '[WIP] Appearance duration'
  }

  get appearanceTimespan(): string {
    return '[WIP] Appearance timespan'
  }

  get categoryLabel(): string {
    return this._occurrence.category_label
  }

  get categoryScore(): number {
    return _.round(this._occurrence.category_score, 2)
  }

  get deployment(): string {
    return this._occurrence.deployment
  }

  get deploymentLocation(): string {
    return '[WIP] Deployment location'
  }

  get familyLabel(): string {
    return '[WIP] Family'
  }

  get id(): string {
    return `#${this._occurrence.id}`
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

  get sessionId(): string {
    return '[WIP] Session ID'
  }

  get sessionTimespan(): string {
    return getCompactDatespanString({
      date1: new Date(),
      date2: new Date(),
    })
  }

  get timestamp(): Date {
    return new Date(this._occurrence.timestamp)
  }
}
