/**
 * Resolution ladder for the zoomable session detail capture.
 *
 * The view keeps a ladder of image tiers — medium (1024) → large (2560) →
 * original — and requests a higher tier whenever the zoom level demands more
 * pixels than the current tier provides. Demand is expressed in device pixels:
 * container CSS width × devicePixelRatio × zoom scale. See issue #1373.
 */

export interface TierSources {
  medium: string
  large: string
  original: string
}

export interface CaptureTier {
  src: string
  /** Native pixel width; null when unknown (original with no stored dimensions). */
  width: number | null
  /**
   * True when src points at the original file, which may carry an EXIF
   * Orientation tag that browsers force-apply, rotating the pixels out of the
   * coordinate space the detection boxes are drawn in.
   */
  isOriginal: boolean
}

/** Must match THUMBNAILS["SIZES"] in config/settings/base.py. */
export const THUMBNAIL_WIDTHS = {
  medium: 1024,
  large: 2560,
}

/**
 * Accept up to 20% upscale before requesting the next tier, so a display
 * marginally wider than a tier does not force the bigger download.
 */
export const TIER_UPSCALE_TOLERANCE = 1.2

export const buildTierLadder = (
  sources: TierSources,
  captureWidth: number | null
): CaptureTier[] => {
  // Thumbnails are never upscaled, so a tier's real width is capped by the
  // original's. A missing thumbnail size falls back to the original URL, in
  // which case the tier's real width is the original's, whatever the nominal
  // thumbnail size says.
  const tierFor = (src: string, thumbnailWidth: number): CaptureTier => {
    if (src === sources.original) {
      return { src, width: captureWidth, isOriginal: true }
    }
    return {
      src,
      width: captureWidth
        ? Math.min(thumbnailWidth, captureWidth)
        : thumbnailWidth,
      isOriginal: false,
    }
  }

  const candidates = [
    tierFor(sources.medium, THUMBNAIL_WIDTHS.medium),
    tierFor(sources.large, THUMBNAIL_WIDTHS.large),
    { src: sources.original, width: captureWidth, isOriginal: true },
  ]

  const unique = candidates.filter(
    (candidate, index) =>
      candidates.findIndex((other) => other.src === candidate.src) === index
  )

  // Sort by real width (unknown last) and keep only tiers that add resolution.
  const sorted = [...unique].sort(
    (a, b) => (a.width ?? Infinity) - (b.width ?? Infinity)
  )

  return sorted.filter((tier, index) => {
    if (index === 0) {
      return true
    }
    const previous = sorted[index - 1]
    if (previous.width === null) {
      return false
    }
    return tier.width === null || tier.width > previous.width
  })
}

/**
 * Smallest tier that satisfies the demand (within the upscale tolerance);
 * the top tier when nothing does.
 */
export const pickTier = (
  tiers: CaptureTier[],
  demand: number
): CaptureTier | null => {
  for (const tier of tiers) {
    if (tier.width === null || demand <= tier.width * TIER_UPSCALE_TOLERANCE) {
      return tier
    }
  }

  return tiers.length ? tiers[tiers.length - 1] : null
}

/**
 * True when the rendered image dimensions are the stored dimensions swapped —
 * the signature of a browser-applied EXIF rotation. Detection boxes are drawn
 * in the stored (raw pixel) space, so a transposed image must not be shown.
 */
export const isTransposed = (
  natural: { width: number; height: number },
  stored: { width: number | null; height: number | null }
): boolean =>
  stored.width !== null &&
  stored.height !== null &&
  stored.width !== stored.height &&
  natural.width === stored.height &&
  natural.height === stored.width
