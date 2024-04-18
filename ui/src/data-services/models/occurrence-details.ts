import _ from 'lodash'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { UserPermission } from 'utils/user/types'
import { Occurrence, ServerOccurrence } from './occurrence'
import { Taxon } from './taxa'

export type ServerOccurrenceDetails = ServerOccurrence & any // TODO: Update this type

export interface Identification {
  applied?: boolean
  id: string
  overridden?: boolean
  taxon: Taxon
  comment?: string
  userPermissions: UserPermission[]
  createdAt: string
}

export interface HumanIdentification extends Identification {
  comment: string
  user: {
    id: string
    name: string
    image?: string
  }
}

export interface MachinePrediction extends Identification {
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

      return date2.getTime() - date1.getTime()
    }

    this._humanIdentifications = this._occurrence.identifications
      .sort(sortByDate)
      .map((i: any) => {
        const taxon = new Taxon(i.taxon)
        const overridden = i.withdrawn
        const applied = taxon.id === this.determinationTaxon.id

        const identification: HumanIdentification = {
          id: `${i.id}`,
          applied,
          overridden,
          taxon,
          user: { id: `${i.user.id}`, name: i.user.name, image: i.user.image },
          comment: i.comment,
          userPermissions: i.user_permissions,
          createdAt: i.created_at,
        }

        return identification
      })

    this._machinePredictions = this._occurrence.predictions
      .sort(sortByDate)
      .map((p: any) => {
        const taxon = new Taxon(p.taxon)
        const overridden = taxon.id !== this.determinationTaxon.id
        const applied = taxon.id === this.determinationTaxon.id

        const prediction: MachinePrediction = {
          id: `${p.id}`,
          applied,
          overridden,
          taxon,
          score: p.score,
          userPermissions: p.user_permissions,
          createdAt: p.created_at,
        }

        return prediction
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
    let label = 'No classification'

    if (classification) {
      label = `${classification.taxon.name} (${_.round(
        classification.score,
        4
      )})`
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
      label: label,
      timeLabel: getFormatedTimeString({
        date: new Date(detection.timestamp),
      }),
    }
  }
}
