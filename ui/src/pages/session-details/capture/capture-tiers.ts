/**
 * Resolution ladder for the zoomable session detail capture.
 *
 * The view keeps a ladder of image tiers — medium (1024) → large (2560) →
 * original — and requests a higher tier whenever the zoom level demands more
 * pixels than the current tier provides. Demand is expressed in device pixels:
 * container CSS width × devicePixelRatio × zoom scale. See issue #1373.
 */

export interface TierSources {
  // Thumbnail sizes are generated on request, so a missing URL means the
  // capture's storage is likely unreachable; the ladder skips that tier.
  medium?: string
  large?: string
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
  // original's.
  const cap = (thumbnailWidth: number) =>
    captureWidth ? Math.min(thumbnailWidth, captureWidth) : thumbnailWidth

  const candidates: CaptureTier[] = []
  if (sources.medium) {
    candidates.push({
      src: sources.medium,
      width: cap(THUMBNAIL_WIDTHS.medium),
      isOriginal: false,
    })
  }
  if (sources.large) {
    candidates.push({
      src: sources.large,
      width: cap(THUMBNAIL_WIDTHS.large),
      isOriginal: false,
    })
  }
  candidates.push({
    src: sources.original,
    width: captureWidth,
    isOriginal: true,
  })

  // Keep only tiers that add resolution over the previous one — this drops
  // the EXIF-risky original whenever the large thumbnail already covers its
  // full size.
  return candidates.reduce((ladder: CaptureTier[], tier) => {
    const previous = ladder[ladder.length - 1]
    if (
      previous &&
      previous.width !== null &&
      tier.width !== null &&
      tier.width <= previous.width
    ) {
      return ladder
    }
    return [...ladder, tier]
  }, [])
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
