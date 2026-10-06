import { Ref } from 'utils/references'
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

/** One setting a job ran with. `label` is the title the task's config schema gives it, else the key. */
export interface ServerHistoryJobSetting {
  key: string
  label: string
  /** The record the setting names, when it names one. */
  ref: Ref | null
  value: unknown
}

export interface ServerHistoryJob {
  /** The settings a post-processing job ran with; null for other jobs. */
  config: Record<string, unknown> | null
  id: number
  name: string
  settings: ServerHistoryJobSetting[]
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

export interface ServerIdentificationDetails {
  agreed_with_identification_id: number | null
  agreed_with_prediction_id: number | null
  comment: string
  withdrawn: boolean
}

export interface ServerPredictionDetails {
  applied_to_id: number | null
  detection_id: number
  /** The result of the run that re-scored and demoted this prediction, when one did. */
  superseded_by_result_id: number | null
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
  /** Data fields that name another record, by field. */
  data_references: Record<string, Ref>
  determination_after: ServerHistoryTaxon | null
  determination_before: ServerHistoryTaxon | null
  /** Whether it is the latest of its kind, not replaced by a later run. */
  kind: Kind
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
export type AlgorithmResultEntry =
  | ClassMaskingResultEntry
  | SizeFilterResultEntry

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
      job?: Ref
      /** The result of the run that demoted this prediction, when one did. */
      supersededBy?: AlgorithmResultEntry
    }
  | { type: 'algorithm_result'; id: string; entry: AlgorithmResultEntry }

/** The result kinds this UI has a card for; results of any other kind are skipped. */
const ALGORITHM_RESULT_KINDS: string[] = ['class_masking', 'size_filter']

export const convertHistoryTaxon = (taxon: ServerHistoryTaxon) =>
  new Taxon({ ...taxon, id: `${taxon.id}`, cover_image_url: null })

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

const toPrediction = (
  entry: PredictionEntry & {
    algorithm: ServerHistoryAlgorithm
    taxon: ServerHistoryTaxon
  },
  determinationTaxonId?: string
): MachinePrediction => {
  const taxon = convertHistoryTaxon(entry.taxon)

  return {
    algorithm: new Algorithm(entry.algorithm),
    applied: taxon.id === determinationTaxonId,
    createdAt: entry.timestamp,
    id: `${entry.id}`,
    overridden: taxon.id !== determinationTaxonId,
    score: entry.score ?? 0,
    taxon,
    terminal: entry.details.terminal,
    userPermissions: [],
  }
}

const isAlgorithmResult = (
  entry: ServerOccurrenceHistoryEntry
): entry is AlgorithmResultEntry =>
  entry.type === 'algorithm_result' &&
  ALGORITHM_RESULT_KINDS.includes(entry.kind)

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
  const results = entries.filter(isAlgorithmResult)

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
            ? toPrediction({ ...entry, algorithm, taxon }, determinationTaxonId)
            : undefined)
        const supersededBy = results.find(
          (result) => result.id === entry.details.superseded_by_result_id
        )
        const job: Ref | undefined = entry.job
          ? { type: 'job', id: entry.job.id, name: entry.job.name }
          : undefined

        return prediction
          ? [{ type: 'prediction', id, prediction, job, supersededBy }]
          : []
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

export interface ResultPrediction {
  applied: boolean
  /** How many classifications the run created on the occurrence; the card shows the best. */
  count: number
  id: string
  score: number
  taxon: Taxon
}

/** The prediction a result stands for: the best classification its run created, if any. */
export const getResultPrediction = (
  entry: AlgorithmResultEntry,
  determinationTaxonId?: string
): ResultPrediction | undefined => {
  const best = entry.classifications.find(
    (classification) => classification.taxon !== null
  )
  if (!best?.taxon) {
    return undefined
  }
  const taxon = convertHistoryTaxon(best.taxon)

  return {
    applied: taxon.id === determinationTaxonId,
    count: entry.classifications.length,
    id: `${best.id}`,
    score: best.score ?? 0,
    taxon,
  }
}

/** Settings the result card already shows in a row of their own. */
const SETTINGS_SHOWN_ELSEWHERE = ['size_threshold']

/** A job's settings to show as rows, leaving out unset ones and those shown elsewhere. */
export const getJobSettings = (
  job: ServerHistoryJob | null
): ServerHistoryJobSetting[] =>
  (job?.settings ?? []).filter(
    ({ key, value }) =>
      value !== null &&
      value !== undefined &&
      !SETTINGS_SHOWN_ELSEWHERE.includes(key)
  )
