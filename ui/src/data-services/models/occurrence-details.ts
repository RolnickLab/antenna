import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'
import { UserPermission } from 'utils/user/types'
import { Algorithm } from './algorithm'
import { Occurrence, ServerOccurrence } from './occurrence'
import { ServerTaxon, Taxon } from './taxa'
import { TrackStats } from './track-stats'

export type ServerOccurrenceDetails = ServerOccurrence & any // TODO: Update this type

export interface ServerFrameName {
  frames: number
  score_max: number | null
  taxon: { id: number; name: string; rank: string } | null
}

export interface ServerGroupingSummary {
  algorithm: { id: number; key: string; name: string } | null
  derived: boolean
  distinct_taxa: number
  duration_seconds: number | null
  frame_names?: ServerFrameName[]
  frames: number
  frames_with_vectors?: number
  id_agreement: number | null
  linked_detections: number
  motion: number
  score_max: number | null
  score_mean: number | null
  score_min: number | null
  size_ratio: number
}

/** Track stats recomputed for the detail view, never stored server-side. */
export interface GroupingSummary extends TrackStats {
  algorithm?: { id: string; key: string; name: string }
  durationSeconds: number | null
  /** Frames with a classification that stored a feature embedding. */
  framesWithVectors?: number
  linkedDetections: number
  scoreMax: number | null
  scoreMean: number | null
  scoreMin: number | null
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
  /** Whether a feature embedding was stored; null when the API did not say. */
  hasFeatures?: boolean | null
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
  cropUrl?: string
  id: string
  timestamp: Date
  timeLabel: string
}

export interface ServerOccurrenceFrame {
  bbox: number[] | null
  capture: {
    id: number
    height: number | null
    url?: string | null
    width: number | null
  } | null
  classifications: ServerFrameClassification[] | null
  frame_index: number
  height: number | null
  id: number
  timestamp: string | null
  url: string | null
  width: number | null
}

/** One detection of an occurrence, as a frame of the track strip. */
export interface OccurrenceFrame {
  captureId?: string
  /** The full capture the crop was cut from, when its image is stored. */
  captureUrl?: string
  frameIndex: number
  frameLabel: FrameLabel
  hasVector?: boolean
  id: string
  image: { src: string; width: number; height: number }
  label: string
  timeLabel: string
}

export interface ServerFrameSummary {
  capture_id: number
  frame_index: number
  id: number
  timestamp: string | null
}

/** The first or last frame of a track, carried by the detail so no page is needed to reach it. */
export interface FrameSummary {
  captureId: string
  frameIndex: number
  id: string
  timeLabel?: string
}

export interface ServerFrameClassification {
  created_at?: string
  /** Null when the endpoint did not annotate the flag, which is not the same as no vector. */
  has_features?: boolean | null
  score?: number | null
  taxon?: ServerTaxon | null
  terminal?: boolean | null
}

/** The machine's own label for one frame; it stays with the detection through a merge. */
export interface FrameLabel {
  score?: number
  taxon?: Taxon
}

/** One distinct frame label in a track. No taxon means the frames have no classification. */
export interface FrameName {
  frames: number
  scoreMax?: number
  taxon?: Taxon
}

const createdAtTime = (classification: ServerFrameClassification) =>
  classification.created_at ? new Date(classification.created_at).getTime() : 0

/** Terminal classifications outrank intermediate ones such as a moth filter; then score, then recency. */
export const getFrameClassification = <T extends ServerFrameClassification>(
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

/**
 * Whether tracking can compare this frame: true if any classification stored a vector,
 * undefined when every classification left the flag unset, false otherwise.
 */
export const frameHasVector = (
  classifications: ServerFrameClassification[] | null | undefined
): boolean | undefined => {
  const flags = (classifications ?? []).map((c) => c.has_features)

  if (flags.some((flag) => flag === true)) {
    return true
  }

  return flags.length && flags.every((flag) => flag == null) ? undefined : false
}

const timeLabelOf = (timestamp?: string | null) =>
  timestamp
    ? getFormatedTimeString({
        date: new Date(timestamp),
        options: { second: true },
      })
    : undefined

/** "Pelosia muscerda ×7, No classification ×2", naming at most `limit` labels. */
export const formatFrameNames = (names: FrameName[], limit = 4): string => {
  const shown = names.slice(0, limit).map(({ frames, taxon }) =>
    translate(STRING.TRACK_FRAME_NAME_COUNT, {
      count: frames,
      name: taxon?.name ?? translate(STRING.TRACK_FRAME_NO_CLASSIFICATION),
    })
  )

  if (names.length > limit) {
    shown.push(
      translate(STRING.TRACK_FRAME_NAMES_MORE, { count: names.length - limit })
    )
  }

  return shown.join(', ')
}

/** Width and height of a `[x1, y1, x2, y2]` box, 0 when the box is malformed. */
const bboxSize = (bbox?: number[]): [number, number] =>
  bbox?.length === 4
    ? [Math.max(bbox[2] - bbox[0], 0), Math.max(bbox[3] - bbox[1], 0)]
    : [0, 0]

export const convertOccurrenceFrame = (
  frame: ServerOccurrenceFrame
): OccurrenceFrame => {
  const classification = getFrameClassification(frame.classifications)
  const frameLabel: FrameLabel = classification?.taxon
    ? {
        score: classification.score ?? undefined,
        taxon: new Taxon(classification.taxon),
      }
    : {}

  return {
    captureId: frame.capture ? `${frame.capture.id}` : undefined,
    captureUrl: frame.capture?.url || undefined,
    frameIndex: frame.frame_index,
    frameLabel,
    hasVector: frameHasVector(frame.classifications),
    id: `${frame.id}`,
    // The bounding box gives the crop's proportions when the crop itself is missing.
    image: {
      src: frame.url ?? '',
      width: frame.width ?? bboxSize(frame.bbox ?? undefined)[0],
      height: frame.height ?? bboxSize(frame.bbox ?? undefined)[1],
    },
    label: frameLabel.taxon
      ? `${frameLabel.taxon.name} (${
          frameLabel.score?.toFixed(2) ?? translate(STRING.VALUE_NOT_AVAILABLE)
        })`
      : translate(STRING.TRACK_FRAME_NO_CLASSIFICATION),
    timeLabel: timeLabelOf(frame.timestamp) ?? '',
  }
}

const convertFrameSummary = (
  summary?: ServerFrameSummary | null
): FrameSummary | undefined =>
  summary
    ? {
        captureId: `${summary.capture_id}`,
        frameIndex: summary.frame_index,
        id: `${summary.id}`,
        timeLabel: timeLabelOf(summary.timestamp),
      }
    : undefined

export class OccurrenceDetails extends Occurrence {
  private readonly _firstPage: OccurrenceFrame[]
  private readonly _humanIdentifications: HumanIdentification[]
  private readonly _machinePredictions: MachinePrediction[]

  public constructor(occurrence: ServerOccurrenceDetails) {
    super(occurrence)

    this._firstPage = (this._occurrence.detections ?? []).map(
      convertOccurrenceFrame
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
        const applied = !!taxon && taxon.id === this.determinationTaxon?.id

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
        const overridden = taxon.id !== this.determinationTaxon?.id
        const applied = taxon.id === this.determinationTaxon?.id

        const prediction: MachinePrediction = {
          id: `${p.id}`,
          applied,
          overridden,
          taxon,
          hasFeatures: p.has_features,
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

  /** The first page of frames, earliest first; the frames endpoint serves the rest. */
  get firstFramesPage(): OccurrenceFrame[] {
    return this._firstPage
  }

  get firstFrame(): FrameSummary | undefined {
    return convertFrameSummary(this._occurrence.first_detection)
  }

  get lastFrame(): FrameSummary | undefined {
    return convertFrameSummary(this._occurrence.last_detection)
  }

  /** Distinct labels across every frame, most frames first. */
  get frameNames(): FrameName[] {
    const names: ServerFrameName[] =
      this._occurrence.grouping_summary?.frame_names ?? []

    return names.map((name) => ({
      frames: name.frames,
      scoreMax: name.score_max ?? undefined,
      taxon: name.taxon
        ? new Taxon({
            cover_image_url: null,
            id: `${name.taxon.id}`,
            name: name.taxon.name,
            rank: name.taxon.rank,
          })
        : undefined,
    }))
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
      framesWithVectors: summary.frames_with_vectors,
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
}
