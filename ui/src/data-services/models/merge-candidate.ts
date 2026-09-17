import { STRING, translate } from 'utils/language'
import { getMatchLevel } from './capture-match'

export type MergeRelation = 'before' | 'after' | 'gap'

export interface ServerMergeCandidate {
  id: number
  determination: { id: number; name: string } | null
  detections_count: number
  first_appearance_timestamp: string | null
  last_appearance_timestamp: string | null
  relation: MergeRelation
  time_offset_seconds: number
  distance: number | null
  similarity: number | null
  cost: number | null
  iou: number | null
  size_ratio: number | null
  likelihood: number | null
  would_link: boolean
  image: string | null
  capture_id: number | null
  image_timestamp: string | null
  edge_image: string | null
  edge_timestamp: string | null
}

/** The candidates plus the tracker settings they were judged by. */
export interface ServerMergeCandidates {
  candidates: ServerMergeCandidate[]
  cost_threshold: number
  requires_features: boolean
}

/** An occurrence that could be merged with another, scored against it by the tracking method. */
export interface MergeCandidate {
  id: string
  displayName: string
  images: { src: string }[]
  numDetections: number
  relation: MergeRelation
  /** Negative when the candidate ends first, positive when it starts later, 0 in a gap of the track. */
  timeOffsetSeconds: number
  /** Centre-to-centre gap of the two nearest frames as a fraction of the frame; null without a box. */
  distance: number | null
  /** Cosine similarity of the two nearest frames; null when either has no feature vector. */
  similarity: number | null
  /** The tracking method's matching cost for the nearest pair; lower fits better. */
  cost: number | null
  /** Overlap of the two nearest boxes, intersection over union. */
  iou: number | null
  /** Area of the smaller box over the larger. */
  sizeRatio: number | null
  /** 0 to 1, 1 the best match: one minus the mean term of the cost. */
  likelihood: number | null
  /** The pair passes the tracker's own rule: under its threshold, with vectors where it requires them. */
  wouldLink: boolean
  /** The capture holding the candidate's nearest frame, the one its crop is cut from. */
  captureId: string | null
  imageTimestamp: Date | null
  /** Crop of this occurrence's own frame in the scored pair: its first frame for a "before" candidate, its last for an "after" one. */
  edgeImage: string | null
  edgeTimestamp: Date | null
}

const toDate = (timestamp: string | null | undefined): Date | null =>
  timestamp ? new Date(timestamp) : null

export const convertMergeCandidate = (
  candidate: ServerMergeCandidate
): MergeCandidate => ({
  id: `${candidate.id}`,
  displayName: candidate.determination
    ? `${candidate.determination.name} #${candidate.id}`
    : `#${candidate.id}`,
  images: candidate.image ? [{ src: candidate.image }] : [],
  numDetections: candidate.detections_count,
  relation: candidate.relation,
  timeOffsetSeconds: candidate.time_offset_seconds,
  distance: candidate.distance,
  similarity: candidate.similarity,
  cost: candidate.cost,
  iou: candidate.iou ?? null,
  sizeRatio: candidate.size_ratio ?? null,
  likelihood: candidate.likelihood ?? null,
  wouldLink: !!candidate.would_link,
  captureId: candidate.capture_id != null ? `${candidate.capture_id}` : null,
  imageTimestamp: toDate(candidate.image_timestamp),
  edgeImage: candidate.edge_image ?? null,
  edgeTimestamp: toDate(candidate.edge_timestamp),
})

export const getOffsetLabel = (seconds: number): string => {
  const total = Math.round(Math.abs(seconds))

  if (total < 60) {
    return translate(STRING.TRACK_OFFSET_SECONDS, { count: total })
  }

  const minutes = Math.round(total / 60)

  if (minutes < 60) {
    return translate(STRING.TRACK_OFFSET_MINUTES, { count: minutes })
  }

  return translate(STRING.TRACK_OFFSET_HOURS, {
    hours: Math.floor(minutes / 60),
    minutes: minutes % 60,
  })
}

export const getWhenLabel = (timeOffsetSeconds: number): string =>
  translate(
    timeOffsetSeconds < 0 ? STRING.TRACK_WHEN_EARLIER : STRING.TRACK_WHEN_LATER,
    { time: getOffsetLabel(timeOffsetSeconds) }
  )

export interface ComparisonSide {
  src: string | null
  timestamp: Date | null
}

/** The two crops of a scored pair in time order, with the gap between them as a signed label. */
export interface ComparisonSides {
  left: ComparisonSide
  right: ComparisonSide
  gapLabel: string
}

/**
 * Seconds from the track frame a candidate is scored against to the candidate's own
 * frame: negative when the candidate is earlier. A gap candidate is measured from the
 * nearest track frame, which can lie on either side of it.
 */
export const getWhenOffsetSeconds = (
  candidate: Pick<
    MergeCandidate,
    'relation' | 'timeOffsetSeconds' | 'imageTimestamp' | 'edgeTimestamp'
  >
): number =>
  candidate.relation === 'gap' &&
  candidate.imageTimestamp &&
  candidate.edgeTimestamp
    ? (candidate.imageTimestamp.getTime() - candidate.edgeTimestamp.getTime()) /
      1000
    : candidate.timeOffsetSeconds

export const getComparisonSides = (
  candidate: MergeCandidate
): ComparisonSides => {
  const candidateSide: ComparisonSide = {
    src: candidate.images[0]?.src ?? null,
    timestamp: candidate.imageTimestamp,
  }
  const edgeSide: ComparisonSide = {
    src: candidate.edgeImage,
    timestamp: candidate.edgeTimestamp,
  }

  const offsetSeconds = getWhenOffsetSeconds(candidate)
  const time = getOffsetLabel(offsetSeconds)

  return offsetSeconds < 0
    ? {
        left: candidateSide,
        right: edgeSide,
        gapLabel: translate(STRING.TRACK_GAP_BEFORE, { time }),
      }
    : {
        left: edgeSide,
        right: candidateSide,
        gapLabel: translate(STRING.TRACK_GAP_AFTER, { time }),
      }
}

export const getDistanceLabel = (distance: number | null): string =>
  distance === null
    ? translate(STRING.VALUE_NOT_AVAILABLE)
    : translate(STRING.TRACK_PERCENT, { percent: (distance * 100).toFixed(1) })

export const getSimilarityLabel = (similarity: number | null): string =>
  similarity === null
    ? translate(STRING.VALUE_NOT_AVAILABLE)
    : translate(STRING.TRACK_PERCENT, {
        percent: `${Math.round(similarity * 100)}`,
      })

/** Overlap and size ratio read as whole percentages, like similarity. */
export const getRatioLabel = getSimilarityLabel

/** The match band and percentage the extend view shows for the same score. */
export const getLikelihoodLabel = (likelihood: number | null): string =>
  likelihood === null
    ? translate(STRING.VALUE_NOT_AVAILABLE)
    : translate(STRING.TRACK_MATCH_SCORE, {
        level: translate(getMatchLevel(likelihood)),
        percent: `${Math.round(likelihood * 100)}`,
      })

/** The cost against the threshold tracking links under, so a reader sees how close the pair came. */
export const getCostLabel = (cost: number | null, threshold?: number): string =>
  cost === null
    ? translate(STRING.VALUE_NOT_AVAILABLE)
    : threshold === undefined
    ? cost.toFixed(2)
    : translate(STRING.TRACK_COST_OF_THRESHOLD, {
        cost: cost.toFixed(2),
        threshold: threshold.toFixed(2),
      })

export type MergeCandidateSortColumn =
  | 'when'
  | 'distance'
  | 'similarity'
  | 'match'

/** One column the reviewer clicked, or all three applied in turn. */
export type MergeCandidateSort =
  | { column: MergeCandidateSortColumn; descending: boolean }
  | { cumulative: true }

const sortValue = (
  candidate: MergeCandidate,
  column: MergeCandidateSortColumn
): number | null =>
  column === 'when'
    ? getWhenOffsetSeconds(candidate)
    : column === 'distance'
    ? candidate.distance
    : column === 'similarity'
    ? candidate.similarity
    : candidate.likelihood

const compare = (
  valueA: number | null,
  valueB: number | null,
  descending: boolean
): number => {
  if (valueA === null || valueB === null) {
    return valueA === valueB ? 0 : valueA === null ? 1 : -1
  }

  return (valueA - valueB) * (descending ? -1 : 1)
}

// Nearest in time first, then closest, then most alike. Time is unsigned here:
// a candidate half a minute either side of the track is equally near it.
const CUMULATIVE_KEYS: {
  descending: boolean
  value: (candidate: MergeCandidate) => number | null
}[] = [
  { descending: false, value: (c) => Math.abs(getWhenOffsetSeconds(c)) },
  { descending: false, value: (c) => c.distance },
  { descending: true, value: (c) => c.similarity },
]

/**
 * Reorder loaded candidates, keeping the server's cost order when no sort is chosen
 * and for rows a sort cannot separate. Rows without a value go last on every key.
 */
export const sortMergeCandidates = (
  candidates: MergeCandidate[],
  sort?: MergeCandidateSort
): MergeCandidate[] => {
  if (!sort) {
    return candidates
  }

  if ('cumulative' in sort) {
    return [...candidates].sort((a, b) => {
      for (const key of CUMULATIVE_KEYS) {
        const result = compare(key.value(a), key.value(b), key.descending)

        if (result !== 0) {
          return result
        }
      }

      return 0
    })
  }

  return [...candidates].sort((a, b) =>
    compare(
      sortValue(a, sort.column),
      sortValue(b, sort.column),
      sort.descending
    )
  )
}
