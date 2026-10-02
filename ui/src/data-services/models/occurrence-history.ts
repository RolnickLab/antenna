import { getUserLabel } from 'utils/user/getUserLabel'
import { Algorithm } from './algorithm'
import { HumanIdentification, MachinePrediction } from './occurrence-details'
import { Taxon } from './taxa'

export interface ServerHistoryTaxon {
  id: number
  name: string
  rank: string
}

export interface ServerHistoryUser {
  id: number
  image: string | null
  name: string
}

export interface ServerHistoryAlgorithm {
  id: number
  key: string
  name: string
}

export interface ServerHistoryJob {
  id: number
  name: string
}

interface ServerDeterminationChangePayload {
  taxon_after_id: number | null
  taxon_before_id: number | null
}

export interface ServerTrackingPayload
  extends ServerDeterminationChangePayload {
  cost_max: number | null
  cost_mean: number | null
  detections_count: number
  feature_algorithm_id: number | null
  frames_linked: number
  occurrences_merged: number[]
  settings: Record<string, unknown>
}

export interface ServerClassMaskingPayload
  extends ServerDeterminationChangePayload {
  detection_ids: number[]
  source_algorithm_id: number
  taxa_list_id: number
}

export interface ServerSizeFilterPayload
  extends ServerDeterminationChangePayload {
  detection_ids: number[]
  size_threshold: number
}

export interface ServerGroupingReviewPayload {
  detection_ids: number[]
  detections_added: number[]
  detections_removed: number[]
  first_timestamp: string | null
  frames_count: number
  last_timestamp: string | null
  occurrence_id?: number | null
  split_from_occurrence_id?: number | null
}

export interface ServerIdentificationPayload {
  agreed_with_identification_id: number | null
  agreed_with_prediction_id: number | null
  comment: string
  withdrawn: boolean
}

export interface ServerPredictionPayload {
  applied_to_id: number | null
  detection_id: number | null
  terminal: boolean | null
}

interface ServerHistoryEntryBase<Type extends string, Subtype, Payload> {
  algorithm: ServerHistoryAlgorithm | null
  comment: string
  id: number
  /** For results and reviews: whether it is the latest of its kind, not replaced. */
  is_current: boolean | null
  job: ServerHistoryJob | null
  payload: Payload
  score: number | null
  subtype: Subtype
  taxon: ServerHistoryTaxon | null
  taxon_before: ServerHistoryTaxon | null
  timestamp: string
  type: Type
  user: ServerHistoryUser | null
  verdict: 'confirmed' | 'rejected' | 'corrected' | null
  withdrawn: boolean
}

export type TrackingResultEntry = ServerHistoryEntryBase<
  'algorithm_result',
  'tracking',
  ServerTrackingPayload
>
export type ClassMaskingResultEntry = ServerHistoryEntryBase<
  'algorithm_result',
  'class_masking',
  ServerClassMaskingPayload
>
export type SizeFilterResultEntry = ServerHistoryEntryBase<
  'algorithm_result',
  'size_filter',
  ServerSizeFilterPayload
>
export type AlgorithmResultEntry =
  | TrackingResultEntry
  | ClassMaskingResultEntry
  | SizeFilterResultEntry
export type GroupingReviewEntry = ServerHistoryEntryBase<
  'review',
  'grouping',
  ServerGroupingReviewPayload
>
export type CommentReviewEntry = ServerHistoryEntryBase<
  'review',
  'comment',
  Record<string, never>
>
export type ReviewEntry = GroupingReviewEntry | CommentReviewEntry
export type IdentificationEntry = ServerHistoryEntryBase<
  'identification',
  null,
  ServerIdentificationPayload
>
export type PredictionEntry = ServerHistoryEntryBase<
  'prediction',
  null,
  ServerPredictionPayload
>

export type ServerOccurrenceHistoryEntry =
  | AlgorithmResultEntry
  | ReviewEntry
  | IdentificationEntry
  | PredictionEntry

export type TimelineItem =
  | {
      type: 'identification'
      id: string
      identification: HumanIdentification
    }
  | { type: 'prediction'; id: string; prediction: MachinePrediction }
  | { type: 'algorithm_result'; id: string; entry: AlgorithmResultEntry }
  | { type: 'review'; id: string; entry: ReviewEntry }

const ALGORITHM_RESULT_SUBTYPES = ['tracking', 'class_masking', 'size_filter']
const REVIEW_SUBTYPES = ['grouping', 'comment']

export const convertHistoryTaxon = (taxon: ServerHistoryTaxon) =>
  new Taxon({ ...taxon, id: `${taxon.id}`, cover_image_url: null })

const toIdentification = (
  entry: IdentificationEntry,
  determinationTaxonId?: string
): HumanIdentification => {
  const taxon = entry.taxon ? convertHistoryTaxon(entry.taxon) : undefined

  return {
    applied: !!taxon && taxon.id === determinationTaxonId,
    comment: entry.payload.comment,
    createdAt: entry.timestamp,
    id: `${entry.id}`,
    overridden: entry.payload.withdrawn,
    taxon,
    user: entry.user
      ? {
          id: `${entry.user.id}`,
          image: entry.user.image ?? undefined,
          name: getUserLabel(entry.user),
        }
      : { name: getUserLabel(entry.user) },
    userPermissions: [],
  }
}

const toPrediction = (
  entry: PredictionEntry & { taxon: ServerHistoryTaxon },
  determinationTaxonId?: string
): MachinePrediction => {
  const taxon = convertHistoryTaxon(entry.taxon)

  return {
    algorithm: entry.algorithm ? new Algorithm(entry.algorithm) : undefined,
    applied: taxon.id === determinationTaxonId,
    createdAt: entry.timestamp,
    id: `${entry.id}`,
    overridden: taxon.id !== determinationTaxonId,
    score: entry.score ?? 0,
    taxon,
    terminal: !!entry.payload.terminal,
    userPermissions: [],
  }
}

/**
 * The history as cards to render, newest first. Identifications and predictions reuse the
 * occurrence's own records when it has them, since only those carry the viewer's permissions.
 */
export const getTimelineItems = ({
  determinationTaxonId,
  entries,
  identifications,
  predictions,
}: {
  determinationTaxonId?: string
  entries: ServerOccurrenceHistoryEntry[]
  identifications: HumanIdentification[]
  predictions: MachinePrediction[]
}): TimelineItem[] =>
  entries.flatMap((entry): TimelineItem[] => {
    const id = `${entry.type}-${entry.id}`

    switch (entry.type) {
      case 'identification': {
        const identification =
          identifications.find((i) => i.id === `${entry.id}`) ??
          toIdentification(entry, determinationTaxonId)

        return [{ type: 'identification', id, identification }]
      }
      case 'prediction': {
        const { taxon } = entry
        const prediction =
          predictions.find((p) => p.id === `${entry.id}`) ??
          (taxon
            ? toPrediction({ ...entry, taxon }, determinationTaxonId)
            : undefined)

        return prediction ? [{ type: 'prediction', id, prediction }] : []
      }
      case 'algorithm_result':
        return ALGORITHM_RESULT_SUBTYPES.includes(entry.subtype)
          ? [{ type: 'algorithm_result', id, entry }]
          : []
      case 'review':
        return REVIEW_SUBTYPES.includes(entry.subtype)
          ? [{ type: 'review', id, entry }]
          : []
      default:
        return []
    }
  })

/**
 * The best prediction of each algorithm: highest score, then terminal, then latest, then id.
 * The occurrence lists every frame tied for an algorithm's top score, and the history keeps one.
 */
const onePredictionPerAlgorithm = (predictions: MachinePrediction[]) => {
  const rank = (p: MachinePrediction) => [
    p.score ?? -Infinity,
    p.terminal ? 1 : 0,
    new Date(p.createdAt).getTime() || 0,
    Number(p.id) || 0,
  ]
  const isBetter = (a: MachinePrediction, b: MachinePrediction) => {
    const [rankA, rankB] = [rank(a), rank(b)]
    const index = rankA.findIndex((value, i) => value !== rankB[i])

    return index !== -1 && rankA[index] > rankB[index]
  }
  const best = new Map<string, MachinePrediction>()
  predictions.forEach((prediction) => {
    const key = `${prediction.algorithm?.id}`
    const current = best.get(key)
    if (!current || isBetter(prediction, current)) {
      best.set(key, prediction)
    }
  })

  return [...best.values()]
}

/**
 * Identifications and predictions merged newest first, for while the history loads or when it is
 * unavailable. Predictions and tie breaks follow the server, so cards keep their place once it arrives.
 */
export const getFallbackTimelineItems = ({
  identifications,
  predictions,
}: {
  identifications: HumanIdentification[]
  predictions: MachinePrediction[]
}): TimelineItem[] =>
  [
    ...identifications.map(
      (identification): TimelineItem => ({
        type: 'identification',
        id: `identification-${identification.id}`,
        identification,
      })
    ),
    ...onePredictionPerAlgorithm(predictions).map(
      (prediction): TimelineItem => ({
        type: 'prediction',
        id: `prediction-${prediction.id}`,
        prediction,
      })
    ),
  ]
    .map((item) => ({
      item,
      time: new Date(getCreatedAt(item)).getTime(),
      id: Number(getSourceId(item)),
    }))
    .sort((a, b) => b.time - a.time || b.id - a.id)
    .map(({ item }) => item)

const getSourceId = (item: TimelineItem) => {
  switch (item.type) {
    case 'identification':
      return item.identification.id
    case 'prediction':
      return item.prediction.id
    default:
      return item.entry.id
  }
}

const getCreatedAt = (item: TimelineItem) => {
  switch (item.type) {
    case 'identification':
      return item.identification.createdAt
    case 'prediction':
      return item.prediction.createdAt
    default:
      return item.entry.timestamp
  }
}

/**
 * The prediction an algorithm result stands in for, so it can still be agreed with. Matched on
 * algorithm alone: the result's taxon is the determination after the run, not what was predicted.
 */
export const getFoldedPrediction = (
  entry: AlgorithmResultEntry,
  predictions: MachinePrediction[]
) =>
  entry.algorithm
    ? predictions.find((p) => `${p.algorithm?.id}` === `${entry.algorithm?.id}`)
    : undefined
