/** Where the track frame the scores compare against sits relative to the capture. */
export type CaptureMatchRelation = 'same' | 'before' | 'after' | 'gap'

export interface ServerCaptureMatch {
  detection_id: number
  occurrence_id: number | null
  in_track: boolean
  likelihood: number | null
  cost: number | null
  distance: number | null
  iou: number | null
  size_ratio: number | null
  similarity: number | null
  time_offset_seconds: number | null
  would_link: boolean
  skipped_reason: 'no_vector' | null
}

export interface ServerCaptureMatches {
  capture_id: number
  cost_threshold: number
  feature_algorithm_id: number | null
  requires_features: boolean
  reference: {
    detection_id: number
    capture_id: number
    timestamp: string
    relation: CaptureMatchRelation
  } | null
  detections: ServerCaptureMatch[]
}

/** How likely one box on a capture is the animal of the track being extended. */
export interface CaptureMatch {
  detectionId: string
  inTrack: boolean
  /** 0 to 1, 1 the best match; null for the track's own frames or with nothing to compare. */
  likelihood: number | null
  /** Centre-to-centre gap as a fraction of the frame diagonal. */
  distance: number | null
  /** Null when either box has no feature vector. */
  similarity: number | null
  timeOffsetSeconds: number | null
  /** Null when the track has no frame on another capture to compare against. */
  relation: CaptureMatchRelation | null
  /** The one box the tracker's own matcher would link the reference frame to. */
  wouldLink: boolean
  /** Why the tracker would leave the box out, even though it is scored. */
  skippedReason: 'no_vector' | null
}

export const convertCaptureMatches = (
  data: ServerCaptureMatches
): Record<string, CaptureMatch> =>
  data.detections.reduce((result: Record<string, CaptureMatch>, row) => {
    result[`${row.detection_id}`] = {
      detectionId: `${row.detection_id}`,
      inTrack: row.in_track,
      likelihood: row.likelihood,
      distance: row.distance,
      similarity: row.similarity,
      timeOffsetSeconds: row.time_offset_seconds,
      relation: data.reference?.relation ?? null,
      wouldLink: !!row.would_link,
      skippedReason: row.skipped_reason ?? null,
    }

    return result
  }, {})
