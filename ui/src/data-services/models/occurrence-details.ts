import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { Algorithm } from './algorithm'
import { Occurrence, ServerOccurrence } from './occurrence'
import { ServerTaxon, Taxon } from './taxa'

export type ServerOccurrenceDetails = ServerOccurrence & any // TODO: Update this type

export interface Identification {
  applied?: boolean
  id: string
  overridden?: boolean
  taxon: Taxon
  comment?: string
  algorithm?: Algorithm
  score?: number
  terminal?: boolean
  userPermissions: UserPermission[]
  createdAt: string
}

export interface HumanIdentification extends Identification {
  comment: string
  user: {
    id?: string
    name: string
    image?: string
  }
}

export interface MachinePrediction extends Identification {
  algorithm: Algorithm
  score: number
  terminal: boolean
}

export interface ServerDetectionClassification {
  created_at?: string
  score?: number | null
  taxon?: ServerTaxon | null
  terminal?: boolean | null
}

/** A detection as the occurrence detail sends it inline. */
export interface ServerOccurrenceDetection {
  bbox: number[] | null
  capture: { id: number; url?: string | null } | null
  classifications: ServerDetectionClassification[] | null
  height: number | null
  id: number
  timestamp: string | null
  url: string | null
  width: number | null
}

/** The machine's own label for one detection. */
export interface DetectionLabel {
  score?: number
  taxon?: Taxon
}

/** One detection of an occurrence, as a row on the occurrence page. */
export interface OccurrenceDetection {
  captureId?: string
  detectionLabel: DetectionLabel
  id: string
  image: { src: string; width: number; height: number }
  label: string
  timestamp?: Date
  timeLabel: string
}

const createdAtTime = (classification: ServerDetectionClassification) =>
  classification.created_at ? new Date(classification.created_at).getTime() : 0

/** Terminal classifications outrank intermediate ones such as a moth filter; then score, then recency. */
export const getDetectionClassification = <
  T extends ServerDetectionClassification
>(
  classifications: T[] | null | undefined
): T | undefined => {
  const named = (classifications ?? []).filter((c) => !!c.taxon)
  const terminal = named.filter((c) => c.terminal === true)

  return (terminal.length ? terminal : named).reduce<T | undefined>(
    (best, c) => {
      if (!best) {
        return c
      }
      const score = c.score ?? -1
      const bestScore = best.score ?? -1
      if (score !== bestScore) {
        return score > bestScore ? c : best
      }
      return createdAtTime(c) > createdAtTime(best) ? c : best
    },
    undefined
  )
}

/** Width and height of a `[x1, y1, x2, y2]` box, 0 when the box is malformed. */
const bboxSize = (bbox?: number[] | null): [number, number] =>
  bbox?.length === 4
    ? [Math.max(bbox[2] - bbox[0], 0), Math.max(bbox[3] - bbox[1], 0)]
    : [0, 0]

export const convertOccurrenceDetection = (
  detection: ServerOccurrenceDetection
): OccurrenceDetection => {
  const classification = getDetectionClassification(detection.classifications)
  const detectionLabel: DetectionLabel = classification?.taxon
    ? {
        score: classification.score ?? undefined,
        taxon: new Taxon(classification.taxon),
      }
    : {}
  const timestamp = detection.timestamp
    ? new Date(detection.timestamp)
    : undefined

  return {
    captureId: detection.capture ? `${detection.capture.id}` : undefined,
    detectionLabel,
    id: `${detection.id}`,
    // The bounding box gives the crop's proportions when the crop itself is missing.
    image: {
      src: detection.url ?? '',
      width: detection.width ?? bboxSize(detection.bbox)[0],
      height: detection.height ?? bboxSize(detection.bbox)[1],
    },
    label: detectionLabel.taxon
      ? `${detectionLabel.taxon.name} (${
          detectionLabel.score?.toFixed(2) ??
          translate(STRING.VALUE_NOT_AVAILABLE)
        })`
      : translate(STRING.DETECTION_NO_CLASSIFICATION),
    timestamp,
    timeLabel: timestamp
      ? getFormatedTimeString({ date: timestamp, options: { second: true } })
      : '',
  }
}

/** Earliest capture first; detections without a time go last, and ids break ties. */
export const sortDetectionsByTime = (
  detections: OccurrenceDetection[]
): OccurrenceDetection[] =>
  [...detections].sort((a, b) => {
    const aTime = a.timestamp?.getTime() ?? Infinity
    const bTime = b.timestamp?.getTime() ?? Infinity
    if (aTime !== bTime) {
      return aTime - bTime
    }

    return Number(a.id) - Number(b.id)
  })

export class OccurrenceDetails extends Occurrence {
  private readonly _detections: OccurrenceDetection[]
  private readonly _humanIdentifications: HumanIdentification[]
  private readonly _machinePredictions: MachinePrediction[]

  public constructor(occurrence: ServerOccurrenceDetails) {
    super(occurrence)

    // The server sends every detection, latest first; the page lists them in capture order.
    this._detections = sortDetectionsByTime(
      (this._occurrence.detections ?? []).map(convertOccurrenceDetection)
    )

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
          user: i.user
            ? {
                id: `${i.user.id}`,
                name: i.user.name?.length
                  ? i.user.name
                  : translate(STRING.ANONYMOUS_USER),
                image: i.user.image,
              }
            : { name: translate(STRING.ANONYMOUS_USER) },
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
          terminal: p.terminal,
          algorithm: p.algorithm,
          userPermissions: p.user_permissions,
          createdAt: p.created_at,
        }

        return prediction
      })
  }

  get endpointURL(): string {
    return this._occurrence.details
  }

  /** Every detection of the occurrence, earliest capture first. */
  get detections(): OccurrenceDetection[] {
    return this._detections
  }

  get humanIdentifications(): HumanIdentification[] {
    return this._humanIdentifications
  }

  get machinePredictions(): MachinePrediction[] {
    return this._machinePredictions
  }

  get rawData(): string {
    return JSON.stringify(this._occurrence, null, 4)
  }
}
