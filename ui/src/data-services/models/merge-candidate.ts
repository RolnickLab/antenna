import { STRING, translate } from 'utils/language'

export type MergeRelation = 'before' | 'after' | 'overlapping'

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
  image: string | null
}

/** An occurrence that could be merged with another, scored against it by the tracking method. */
export interface MergeCandidate {
  id: string
  displayName: string
  images: { src: string }[]
  numDetections: number
  relation: MergeRelation
  /** Negative when the candidate ends first, positive when it starts later, 0 when they overlap. */
  timeOffsetSeconds: number
  /** Centre-to-centre gap of the two nearest frames as a fraction of the frame; null without a box. */
  distance: number | null
  /** Cosine similarity of the two nearest frames; null when either has no feature vector. */
  similarity: number | null
  cost: number | null
}

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
})

const getOffsetLabel = (seconds: number): string => {
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

export const getWhenLabel = (
  relation: MergeRelation,
  timeOffsetSeconds: number
): string => {
  if (relation === 'overlapping') {
    return translate(STRING.TRACK_WHEN_OVERLAPS)
  }

  return translate(
    relation === 'before' ? STRING.TRACK_WHEN_EARLIER : STRING.TRACK_WHEN_LATER,
    { time: getOffsetLabel(timeOffsetSeconds) }
  )
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

export type MergeCandidateSortColumn = 'when' | 'distance' | 'similarity'

export interface MergeCandidateSort {
  column: MergeCandidateSortColumn
  descending: boolean
}

const sortValue = (
  candidate: MergeCandidate,
  column: MergeCandidateSortColumn
): number | null =>
  column === 'when'
    ? candidate.timeOffsetSeconds
    : column === 'distance'
    ? candidate.distance
    : candidate.similarity

/**
 * Reorder loaded candidates for one column, keeping the server's cost order when
 * no sort is chosen. Rows without a value for the column go last either way.
 */
export const sortMergeCandidates = (
  candidates: MergeCandidate[],
  sort?: MergeCandidateSort
): MergeCandidate[] => {
  if (!sort) {
    return candidates
  }

  const direction = sort.descending ? -1 : 1

  return [...candidates].sort((a, b) => {
    const valueA = sortValue(a, sort.column)
    const valueB = sortValue(b, sort.column)

    if (valueA === null || valueB === null) {
      return valueA === valueB ? 0 : valueA === null ? 1 : -1
    }

    return (valueA - valueB) * direction
  })
}
