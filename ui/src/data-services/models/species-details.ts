import _ from 'lodash'
import { getCompactTimespanString } from 'utils/date/getCompactTimespanString/getCompactTimespanString'
import { ServerSpecies, Species } from './species'

export type ServerSpeciesDetails = ServerSpecies & any // TODO: Update this type

export class SpeciesDetails extends Species {
  private readonly _occurrences: string[] = []

  public constructor(species: ServerSpeciesDetails) {
    super(species)
    this._occurrences = this._species.occurrences.map((d: any) => `${d.id}`)
  }

  get occurrences(): string[] {
    return this._occurrences
  }

  getOccurrenceInfo(id: string) {
    const occurrence = this._species.occurrences.find(
      (d: any) => `${d.id}` === id
    )

    if (!occurrence) {
      return
    }

    return {
      id,
      image: {
        src: occurrence.best_detection.url,
        width: occurrence.best_detection.width,
        height: occurrence.best_detection.height,
      },
      label: `${occurrence.event.name}\n ${occurrence.determination.name
        } (${_.round(occurrence.determination_score, 4)})`,
      timeLabel: getCompactTimespanString({
        date1: new Date(occurrence.first_appearance_timestamp),
        date2: new Date(occurrence.last_appearance_timestamp),
      }),
      countLabel: `${occurrence.detections_count}`,
    }
  }
}
