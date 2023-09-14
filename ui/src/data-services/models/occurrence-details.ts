import _ from 'lodash'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { Occurrence, ServerOccurrence } from './occurrence'

export type ServerOccurrenceDetails = ServerOccurrence & any // TODO: Update this type

interface Identification {
  id: string
  overridden: boolean
  name: string
  ranks: {
    id: string
    name: string
    rank: string
  }[]
}

interface HumanIdentification extends Identification {
  user: {
    name: string
    image?: string
  }
}

interface MachinePrediction extends Identification {
  score: number
}

export class OccurrenceDetails extends Occurrence {
  private readonly _detections: string[] = []
  private readonly _humanIdentifications: HumanIdentification[]
  private readonly _machinePredictions: MachinePrediction[]

  public constructor(occurrence: ServerOccurrenceDetails) {
    super(occurrence)

    this._detections = this._occurrence.detections.map((d: any) => `${d.id}`)

    const sortByDate = (i1: any, i2: any) => {
      const date1 = new Date(i1.created_at)
      const date2 = new Date(i2.created_at)

      return date1.getTime() - date2.getTime()
    }

    this._humanIdentifications = this._occurrence.identifications
      .sort(sortByDate)
      .map((i: any) => {
        const identification: HumanIdentification = {
          id: `${i.id}`,
          overridden: `${i.taxon.id}` !== this.determinationId,
          name: i.taxon.name,
          ranks: this._getRanks(i.taxon),
          user: { name: i.user.name, image: i.user.image },
        }

        return identification
      })

    this._machinePredictions = this._occurrence.predictions
      .sort(sortByDate)
      .map((i: any) => {
        const identification: MachinePrediction = {
          id: `${i.id}`,
          overridden: `${i.taxon.id}` !== this.determinationId,
          name: i.taxon.name,
          ranks: this._getRanks(i.taxon),
          score: i.score,
        }

        return identification
      })
  }

  get detections(): string[] {
    return this._detections
  }

  get humanIdentifications(): HumanIdentification[] {
    return this._humanIdentifications
  }

  get machinePredictions(): MachinePrediction[] {
    return this._machinePredictions
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
