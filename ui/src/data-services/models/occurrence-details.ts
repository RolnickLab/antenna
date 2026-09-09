import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { Algorithm } from './algorithm'
import { Occurrence, ServerOccurrence } from './occurrence'
import { Taxon } from './taxa'
import { TrackStats } from './track-stats'

export type ServerOccurrenceDetails = ServerOccurrence & any // TODO: Update this type

export interface ServerGroupingSummary {
  algorithm: { id: number; key: string; name: string } | null
  derived: boolean
  distinct_taxa: number
  duration_seconds: number | null
  frames: number
  id_agreement: number | null
  linked_detections: number
  motion: number
  score_max: number
  score_mean: number
  score_min: number
  size_ratio: number
}

/** Track stats recomputed for the detail view, never stored server-side. */
export interface GroupingSummary extends TrackStats {
  algorithm?: { id: string; key: string; name: string }
  durationSeconds: number | null
  linkedDetections: number
  scoreMax: number
  scoreMean: number
  scoreMin: number
}

export interface Identification {
  applied?: boolean
  id: string
  overridden?: boolean
  /** Absent on a comment-only identification. */
  taxon?: Taxon
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
  taxon: Taxon
  terminal: boolean
}

export interface TrackFrame {
  bbox: number[]
  /** Stored dimensions of this frame's own capture, which its bbox is measured in. */
  captureHeight?: number
  captureId?: string
  captureWidth?: number
  id: string
  timestamp: Date
  timeLabel: string
}

export class OccurrenceDetails extends Occurrence {
  private readonly _frames: TrackFrame[] = []
  private readonly _humanIdentifications: HumanIdentification[]
  private readonly _machinePredictions: MachinePrediction[]

  public constructor(occurrence: ServerOccurrenceDetails) {
    super(occurrence)

    // Sorted here rather than taken in payload order: the track editing actions
    // describe a split as "this frame and everything later in time", so the order
    // the frames are listed in has to be a property of this model, not of whatever
    // ordering the endpoint happens to prefetch. See #1272.
    this._frames = this._occurrence.detections
      .map((d: any) => ({
        bbox: d.bbox ?? [],
        captureHeight: d.capture?.height ?? undefined,
        captureId: d.capture?.id !== undefined ? `${d.capture.id}` : undefined,
        captureWidth: d.capture?.width ?? undefined,
        id: `${d.id}`,
        timestamp: new Date(d.timestamp),
        timeLabel: getFormatedTimeString({
          date: new Date(d.timestamp),
          options: { second: true },
        }),
      }))
      .sort(
        (f1: TrackFrame, f2: TrackFrame) =>
          f2.timestamp.getTime() - f1.timestamp.getTime()
      )

    const sortByDate = (i1: any, i2: any) => {
      const date1 = new Date(i1.created_at)
      const date2 = new Date(i2.created_at)

      return date2.getTime() - date1.getTime()
    }

    this._humanIdentifications = this._occurrence.identifications
      .sort(sortByDate)
      .map((i: any) => {
        const taxon = i.taxon ? new Taxon(i.taxon) : undefined
        const overridden = i.withdrawn
        const applied = taxon?.id === this.determinationTaxon.id

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

  get detections(): string[] {
    return this._frames.map((frame) => frame.id)
  }

  /** Detections of this occurrence, newest first — the order the strip renders them in. */
  get frames(): TrackFrame[] {
    return this._frames
  }

  get groupingVerified(): boolean {
    return !!this._occurrence.grouping_verified
  }

  get groupingVerifiedAt(): Date | undefined {
    return this._occurrence.grouping_verified_at
      ? new Date(this._occurrence.grouping_verified_at)
      : undefined
  }

  get groupingVerifiedBy():
    | { id: string; image?: string; name: string }
    | undefined {
    const user = this._occurrence.grouping_verified_by

    if (!user) {
      return undefined
    }

    return {
      id: `${user.id}`,
      image: user.image ?? undefined,
      name: user.name?.length ? user.name : translate(STRING.ANONYMOUS_USER),
    }
  }

  get groupingSummary(): GroupingSummary | undefined {
    const summary: ServerGroupingSummary | null | undefined =
      this._occurrence.grouping_summary

    if (!summary) {
      return undefined
    }

    return {
      algorithm: summary.algorithm
        ? {
            id: `${summary.algorithm.id}`,
            key: summary.algorithm.key,
            name: summary.algorithm.name,
          }
        : undefined,
      distinctTaxa: summary.distinct_taxa,
      durationSeconds: summary.duration_seconds,
      frames: summary.frames,
      idAgreement: summary.id_agreement,
      linkedDetections: summary.linked_detections,
      motion: summary.motion,
      scoreMax: summary.score_max,
      scoreMean: summary.score_mean,
      scoreMin: summary.score_min,
      sizeRatio: summary.size_ratio,
    }
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

  getDetectionInfo(id: string) {
    const detection = this._occurrence.detections.find(
      (d: any) => `${d.id}` === id
    )

    const classification = detection?.classifications?.[0]
    let label = 'No classification'

    if (classification) {
      label = `${classification.taxon.name} (${classification.score.toFixed(
        2
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
        options: { second: true },
      }),
    }
  }
}
