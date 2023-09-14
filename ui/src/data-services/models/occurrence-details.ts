import _ from 'lodash'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { Occurrence, ServerOccurrence } from './occurrence'

export type ServerOccurrenceDetails = ServerOccurrence & any // TODO: Update this type

type Identification = {
  id: string
  overridden: boolean
  name: string
  ranks: {
    id: string
    name: string
    rank: string
  }[]
  user?: {
    name: string
    image?: string
  }
}

export class OccurrenceDetails extends Occurrence {
  private readonly _detections: string[] = []
  private readonly _identifications: Identification[]

  public constructor(occurrence: ServerOccurrenceDetails) {
    super(occurrence)

    this._detections = this._occurrence.detections.map((d: any) => `${d.id}`)

    this._identifications = [
      ...this._occurrence.identifications,
      ...this._occurrence.predictions,
    ].map((i: any) => {
      const taxonId = `${i.taxon.id}`

      return {
        id: `${i.id}`,
        overridden: taxonId !== this.determinationId,
        name: i.taxon.name,
        ranks: this._getRanks(i.taxon),
        user: i.user
          ? {
              name: i.user.name,
              image: i.user.image,
            }
          : undefined,
      }
    })
  }

  get detections(): string[] {
    return this._detections
  }

  get identifications(): Identification[] {
    return this._identifications
  }

  getDetectionInfo(id: string) {
    const detection = this._occurrence.detections.find(
      (d: any) => `${d.id}` === id
    )

    const classification = detection?.classifications?.[0]

    if (!classification) {
      return
    }

    return {
      id,
      captureId:
        detection.capture?.id !== undefined
          ? `${detection.capture.id}`
          : undefined,
      image: {
        src: detection.url,
        width: detection.width,
        height: detection.height,
      },
      label: `${classification.taxon.name} (${_.round(
        classification.score,
        4
      )})`,
      timeLabel: getFormatedTimeString({
        date: new Date(detection.timestamp),
      }),
    }
  }

  private _getRanks = (
    taxon: any
  ): {
    id: string
    name: string
    rank: string
  }[] => {
    const result = []

    let current = taxon
    while (current) {
      result.push({
        id: `${current.id}`,
        name: current.name,
        rank: current.rank,
      })
      current = current.parent
    }

    return result.reverse()
  }
}
