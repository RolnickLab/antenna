import { STRING, translate } from 'utils/language'

export interface ServerTrackStats {
  distinct_taxa: number
  frames: number
  id_agreement: number | null
  motion: number
  size_ratio: number
}

/** How an occurrence's detections move, grow and agree across its frames. */
export interface TrackStats {
  distinctTaxa: number
  frames: number
  /** Share of terminal classifications agreeing with the determination; null without any. */
  idAgreement: number | null
  /** Distance travelled as a fraction of the frame diagonal; 0 is stationary. */
  motion: number
  /** Largest box area over the smallest; 1 is a constant size. */
  sizeRatio: number
}

export const convertTrackStats = (
  stats?: ServerTrackStats | null
): TrackStats | undefined =>
  stats
    ? {
        distinctTaxa: stats.distinct_taxa,
        frames: stats.frames,
        idAgreement: stats.id_agreement,
        motion: stats.motion,
        sizeRatio: stats.size_ratio,
      }
    : undefined

// Movement and growth only mean something once there are two frames to compare.
const hasTrack = (stats?: TrackStats): stats is TrackStats =>
  !!stats && stats.frames >= 2

export const getMotionLabel = (stats?: TrackStats): string | undefined =>
  hasTrack(stats)
    ? translate(STRING.TRACK_STAT_MOTION, {
        percent: (stats.motion * 100).toFixed(1),
      })
    : undefined

export const getSizeChangeLabel = (stats?: TrackStats): string | undefined =>
  hasTrack(stats)
    ? translate(STRING.TRACK_STAT_SIZE_RATIO, {
        ratio: stats.sizeRatio.toFixed(2),
      })
    : undefined

export const getIdAgreementLabel = (stats?: TrackStats): string | undefined => {
  if (!stats || stats.idAgreement === null) {
    return undefined
  }

  const agreement = translate(STRING.TRACK_STAT_ID_AGREEMENT, {
    percent: `${Math.round(stats.idAgreement * 100)}`,
  })

  if (stats.distinctTaxa > 1) {
    return `${agreement} · ${translate(STRING.TRACK_STAT_DISTINCT_TAXA, {
      count: stats.distinctTaxa,
    })}`
  }

  return agreement
}

export const getDurationLabel = (
  seconds: number | null
): string | undefined => {
  if (seconds === null || !Number.isFinite(seconds)) {
    return undefined
  }

  const total = Math.round(seconds)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  const remainder = `${total % 60}`.padStart(2, '0')

  return hours > 0
    ? `${hours}:${`${minutes}`.padStart(2, '0')}:${remainder}`
    : `${minutes}:${remainder}`
}
