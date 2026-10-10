import { STRING, translate } from 'utils/language'
import { ServerModelRef } from 'utils/model-references'
import { getUserLabel } from 'utils/user/getUserLabel'
import { Algorithm } from './algorithm'
import { HumanIdentification, MachinePrediction } from './occurrence-details'
import { Taxon } from './taxa'

/*
 * The server types below mirror the OccurrenceHistoryEntry components in the OpenAPI schema;
 * replace them with generated types when the UI adopts OpenAPI generation.
 */

export interface ServerHistoryTaxon {
  id: number
  name: string
  /** The taxon's ancestors, highest rank first. */
  parents?: { id: number; name: string; rank: string }[]
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

/** One field of a job's config. `label` is the title the task's config schema gives it, else the key. */
export interface ServerJobConfigField {
  key: string
  label: string
  /** The records the field names: one per id it holds, in order. */
  refs: ServerModelRef[]
  value: unknown
}

export interface ServerHistoryJob {
  id: number
  name: string
  config: ServerJobConfigField[]
}

/** The classification a run's classification replaced, when there was one and it still exists. */
export interface ServerReplacedClassification {
  id: number
  score: number | null
  taxon: ServerHistoryTaxon | null
}

/** A classification a post-processing run created, listed inside the run's result. */
export interface ServerCreatedClassification {
  detection_id: number
  id: number
  replaced: ServerReplacedClassification | null
  score: number | null
  /** Null when the taxon was deleted. */
  taxon: ServerHistoryTaxon | null
  terminal: boolean
}

interface ServerDeterminationSnapshot {
  determination_after_id: number | null
  determination_before_id: number | null
  /** Whatever else the method returned; stored as JSON and not interpreted. */
  extra: Record<string, unknown>
}

export interface ClassMaskingResultData extends ServerDeterminationSnapshot {
  /** The share of the source classifier's probability outside the species list. */
  excluded_probability: number
  /** Where the class that wins after masking ranked before it; 1 means it was already the top. */
  new_winner_original_rank: number | null
}

export interface SizeFilterResultData extends ServerDeterminationSnapshot {
  /** The filtered detection's box area as a fraction of its image. */
  relative_size: number
}
/** A taxon the machine labels named, with its name copied when the run recorded it. */
export interface TrackingTaxonLabels {
  taxon_id: number
  name: string
  /** Detections whose best classification names the taxon, and the mean and best score of those labels. */
  detection_count: number
  score_mean?: number | null
  score_max: number | null
}

export interface TrackingResultData extends ServerDeterminationSnapshot {
  detection_count: number
  /** Distinct taxa among the detections' best classifications at the time of the run. */
  distinct_taxa: number
  /** The share of detections whose best classification names the determination after the run; null when none has one. */
  label_agreement: number | null
  /** Each of those distinct taxa, most detections first; missing on results recorded before it existed. */
  taxa?: TrackingTaxonLabels[]
  /** Seconds from the first capture to the last; null when fewer than two have a time. */
  duration_seconds?: number | null
  /** The lowest, mean and highest score of the detections' labels; null when no label has a score. */
  score_min?: number | null
  score_mean?: number | null
  score_max?: number | null
  /** One entry per detection in detection_ids: the cost of the link the run made from it, or null. */
  link_costs: (number | null)[]
  /** Occurrences the run folded into this one; they no longer exist. */
  merged_occurrence_ids: number[]
  /** The mean distance per step between detection centres as a fraction of the image diagonal. */
  motion: number
  /** The total distance between detection centres as a fraction of the image diagonal. */
  path_length: number
  /** The largest box area over the smallest. */
  size_change: number
  /** The grouping before the run: the detections in capture order and the occurrence each was in. */
  detection_ids?: number[]
  previous_occurrence_ids?: (number | null)[]
  /** Identifications moved here, as [identification id, earlier occurrence id]. */
  moved_identifications?: [number, number][]
  withdrawn_identification_ids?: number[]
}

export interface ServerIdentificationDetails {
  comment: string
  withdrawn: boolean
}

export interface ServerPredictionDetails {
  terminal: boolean
}

/** The fields every entry has. */
interface ServerHistoryEntryBase {
  algorithm: ServerHistoryAlgorithm | null
  id: number
  job: ServerHistoryJob | null
  /** A prediction's score; null for other entries. */
  score: number | null
  /** The identified or predicted taxon; null for a result. */
  taxon: ServerHistoryTaxon | null
  timestamp: string
  user: ServerHistoryUser | null
}

interface ServerResultEntry<Kind extends string, Data>
  extends ServerHistoryEntryBase {
  /** The classifications the run created, best score first. */
  classifications: ServerCreatedClassification[]
  data: Data
  determination_after: ServerHistoryTaxon | null
  determination_before: ServerHistoryTaxon | null
  kind: Kind
  /** Other results of the same run, brought here by merging occurrences; `classifications` covers them all. */
  results_merged_in: number
  type: 'algorithm_result'
  /** The kind's headline figure, for sorting and filtering; not a confidence. */
  value: number | null
}

export type ClassMaskingResultEntry = ServerResultEntry<
  'class_masking',
  ClassMaskingResultData
>
export type SizeFilterResultEntry = ServerResultEntry<
  'size_filter',
  SizeFilterResultData
>
export type TrackingResultEntry = ServerResultEntry<
  'tracking',
  TrackingResultData
>
export type AlgorithmResultEntry =
  | ClassMaskingResultEntry
  | SizeFilterResultEntry
  | TrackingResultEntry

export interface IdentificationEntry extends ServerHistoryEntryBase {
  details: ServerIdentificationDetails
  type: 'identification'
}

export interface PredictionEntry extends ServerHistoryEntryBase {
  details: ServerPredictionDetails
  type: 'prediction'
}

export type ServerOccurrenceHistoryEntry =
  | AlgorithmResultEntry
  | IdentificationEntry
  | PredictionEntry

export type TimelineItem =
  | {
      type: 'identification'
      id: string
      identification: HumanIdentification
    }
  | {
      type: 'prediction'
      id: string
      prediction: MachinePrediction
      /** The job that wrote the prediction, when the history names one. */
      job?: ServerModelRef
    }
  | { type: 'algorithm_result'; id: string; entry: AlgorithmResultEntry }

/** The result kinds this UI has a card for, with their names; results of any other kind are skipped. */
const RESULT_KIND_LABELS: Record<AlgorithmResultEntry['kind'], STRING> = {
  class_masking: STRING.HISTORY_CLASS_MASKING,
  size_filter: STRING.HISTORY_SIZE_FILTER,
  tracking: STRING.HISTORY_TRACKING,
}

/** What to call a result's kind, e.g. "Class masking". */
export const getResultKindLabel = (entry: AlgorithmResultEntry) =>
  translate(RESULT_KIND_LABELS[entry.kind])

export const convertHistoryTaxon = (taxon: ServerHistoryTaxon) =>
  new Taxon({
    ...taxon,
    id: `${taxon.id}`,
    cover_image_url: null,
    parents: taxon.parents?.map((parent) => ({
      ...parent,
      id: `${parent.id}`,
      cover_image_url: null,
    })),
  })

const toIdentification = (
  entry: IdentificationEntry & { taxon: ServerHistoryTaxon },
  determinationTaxonId?: string
): HumanIdentification => {
  const taxon = convertHistoryTaxon(entry.taxon)

  return {
    applied: taxon.id === determinationTaxonId,
    comment: entry.details.comment,
    createdAt: entry.timestamp,
    id: `${entry.id}`,
    overridden: entry.details.withdrawn,
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

/** A prediction built from the history, for when the occurrence has no record of its own for it. */
const toPrediction = (
  {
    algorithm,
    id,
    score,
    taxon: historyTaxon,
    terminal,
    timestamp,
  }: {
    algorithm: ServerHistoryAlgorithm
    id: number
    score: number | null
    taxon: ServerHistoryTaxon
    terminal: boolean
    timestamp: string
  },
  determinationTaxonId?: string
): MachinePrediction => {
  const taxon = convertHistoryTaxon(historyTaxon)

  return {
    algorithm: new Algorithm(algorithm),
    applied: taxon.id === determinationTaxonId,
    createdAt: timestamp,
    id: `${id}`,
    overridden: taxon.id !== determinationTaxonId,
    score: score ?? 0,
    taxon,
    terminal,
    userPermissions: [],
  }
}

const isAlgorithmResult = (
  entry: ServerOccurrenceHistoryEntry
): entry is AlgorithmResultEntry =>
  entry.type === 'algorithm_result' && entry.kind in RESULT_KIND_LABELS

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
}): TimelineItem[] => {
  return entries.flatMap((entry): TimelineItem[] => {
    const id = `${entry.type}-${entry.id}`

    switch (entry.type) {
      case 'identification': {
        const { taxon } = entry
        const identification =
          identifications.find((i) => i.id === `${entry.id}`) ??
          (taxon
            ? toIdentification({ ...entry, taxon }, determinationTaxonId)
            : undefined)

        return identification
          ? [{ type: 'identification', id, identification }]
          : []
      }
      case 'prediction': {
        const { algorithm, taxon } = entry
        const prediction =
          predictions.find((p) => p.id === `${entry.id}`) ??
          (algorithm && taxon
            ? toPrediction(
                {
                  ...entry,
                  algorithm,
                  taxon,
                  terminal: entry.details.terminal,
                },
                determinationTaxonId
              )
            : undefined)
        const job: ServerModelRef | undefined = entry.job
          ? { type: 'job', id: entry.job.id, name: entry.job.name }
          : undefined

        return prediction ? [{ type: 'prediction', id, prediction, job }] : []
      }
      case 'algorithm_result':
        return isAlgorithmResult(entry)
          ? [{ type: 'algorithm_result', id, entry }]
          : []
      default:
        return []
    }
  })
}

/**
 * The best prediction of each algorithm: highest score, then terminal, then latest, then id.
 * The occurrence lists every detection tied for an algorithm's top score, and the history keeps one.
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
 * The prediction a result stands for: the best classification its run created, if any. The
 * occurrence's own record is used when it has one, since only that carries the viewer's permissions.
 */
export const getResultPrediction = (
  entry: AlgorithmResultEntry,
  predictions: MachinePrediction[],
  determinationTaxonId?: string
): MachinePrediction | undefined => {
  const best = entry.classifications.find(
    (classification) => classification.taxon !== null
  )
  if (!best?.taxon || !entry.algorithm) {
    return undefined
  }
  return (
    predictions.find((p) => p.id === `${best.id}`) ??
    toPrediction(
      {
        ...best,
        algorithm: entry.algorithm,
        taxon: best.taxon,
        timestamp: entry.timestamp,
      },
      determinationTaxonId
    )
  )
}

/** One field of a job's config, when the job set it. */
export const getJobConfigField = (job: ServerHistoryJob | null, key: string) =>
  job?.config.find((field) => field.key === key)

/** Config fields the result card already shows in a row of their own. */
const CONFIG_SHOWN_ELSEWHERE = ['size_threshold']

/** Config fields listing sessions, of which a card names only the occurrence's own. */
const SESSION_LIST_CONFIG = ['event_ids']

/**
 * A job's config fields to show as rows, leaving out unset ones and those shown elsewhere. With
 * `sessionId`, a list of sessions keeps only that one, since a run's other sessions say nothing about
 * the occurrence, and is left out when it does not name it.
 */
export const getJobConfigFields = (
  job: ServerHistoryJob | null,
  sessionId?: string
): ServerJobConfigField[] =>
  (job?.config ?? [])
    .map((field) =>
      sessionId !== undefined && SESSION_LIST_CONFIG.includes(field.key)
        ? {
            ...field,
            refs: field.refs.filter((ref) => `${ref.id}` === sessionId),
          }
        : field
    )
    .filter(
      ({ key, value, refs }) =>
        value !== null &&
        value !== undefined &&
        !CONFIG_SHOWN_ELSEWHERE.includes(key) &&
        !(SESSION_LIST_CONFIG.includes(key) && !refs.length)
    )
