import {
  buildTierLadder,
  isTransposed,
  pickTier,
  TierSources,
} from './capture-tiers'

const SOURCES: TierSources = {
  medium: 'https://example.org/thumbnails/medium/capture.jpg',
  large: 'https://example.org/thumbnails/large/capture.jpg',
  original: 'https://example.org/captures/capture.jpg',
}

describe('buildTierLadder', () => {
  test('full ladder for a large original: medium, large, original', () => {
    const tiers = buildTierLadder(SOURCES, 4096)

    expect(tiers).toEqual([
      { src: SOURCES.medium, width: 1024, isOriginal: false },
      { src: SOURCES.large, width: 2560, isOriginal: false },
      { src: SOURCES.original, width: 4096, isOriginal: true },
    ])
  })

  test('drops the original when the large thumbnail already covers it', () => {
    // A 2000px original produces a 2000px "large" thumbnail (thumbnails are
    // never upscaled), so the EXIF-risky original adds no resolution.
    const tiers = buildTierLadder(SOURCES, 2000)

    expect(tiers).toEqual([
      { src: SOURCES.medium, width: 1024, isOriginal: false },
      { src: SOURCES.large, width: 2000, isOriginal: false },
    ])
  })

  test('collapses to a single tier when the original is small', () => {
    const tiers = buildTierLadder(SOURCES, 800)

    expect(tiers).toEqual([
      { src: SOURCES.medium, width: 800, isOriginal: false },
    ])
  })

  test('keeps the original as an unknown-width top tier when dimensions are missing', () => {
    const tiers = buildTierLadder(SOURCES, null)

    expect(tiers).toEqual([
      { src: SOURCES.medium, width: 1024, isOriginal: false },
      { src: SOURCES.large, width: 2560, isOriginal: false },
      { src: SOURCES.original, width: null, isOriginal: true },
    ])
  })

  test('missing medium thumbnail falls back to original and sorts by real width', () => {
    // When a thumbnail size is missing, the model getters fall back to the
    // original URL — that tier's real width is the original's, not 1024.
    const sources = { ...SOURCES, medium: SOURCES.original }
    const tiers = buildTierLadder(sources, 4096)

    expect(tiers).toEqual([
      { src: SOURCES.large, width: 2560, isOriginal: false },
      { src: SOURCES.original, width: 4096, isOriginal: true },
    ])
  })

  test('all thumbnails missing yields a single original tier', () => {
    const sources = {
      medium: SOURCES.original,
      large: SOURCES.original,
      original: SOURCES.original,
    }
    const tiers = buildTierLadder(sources, 3000)

    expect(tiers).toEqual([
      { src: SOURCES.original, width: 3000, isOriginal: true },
    ])
  })
})

describe('pickTier', () => {
  const tiers = buildTierLadder(SOURCES, 4096)

  test('accepts up to 20% upscale before stepping up', () => {
    // 1024 * 1.2 = 1228.8 — a 1200px demand stays on medium.
    expect(pickTier(tiers, 1200)?.src).toBe(SOURCES.medium)
    expect(pickTier(tiers, 1300)?.src).toBe(SOURCES.large)
  })

  test('picks medium on a 1x laptop and large on a retina display', () => {
    expect(pickTier(tiers, 1100 * 1)?.src).toBe(SOURCES.medium)
    expect(pickTier(tiers, 1100 * 2)?.src).toBe(SOURCES.large)
  })

  test('high zoom demand reaches the original', () => {
    expect(pickTier(tiers, 4000)?.src).toBe(SOURCES.original)
  })

  test('demand beyond every tier returns the top tier', () => {
    expect(pickTier(tiers, 100000)?.src).toBe(SOURCES.original)
  })

  test('unknown-width tier satisfies any demand', () => {
    const openEnded = buildTierLadder(SOURCES, null)
    expect(pickTier(openEnded, 100000)?.src).toBe(SOURCES.original)
  })

  test('returns null for an empty ladder', () => {
    expect(pickTier([], 1000)).toBeNull()
  })
})

describe('isTransposed', () => {
  test('detects a browser-rotated portrait original', () => {
    // Stored dimensions are raw pixel space; the browser applied the EXIF
    // Orientation tag and swapped the rendered dimensions.
    expect(
      isTransposed({ width: 3456, height: 4608 }, { width: 4608, height: 3456 })
    ).toBe(true)
  })

  test('matching dimensions are not transposed', () => {
    expect(
      isTransposed({ width: 4608, height: 3456 }, { width: 4608, height: 3456 })
    ).toBe(false)
  })

  test('square images can never be flagged', () => {
    expect(
      isTransposed({ width: 2000, height: 2000 }, { width: 2000, height: 2000 })
    ).toBe(false)
  })

  test('unknown stored dimensions are never flagged', () => {
    expect(
      isTransposed({ width: 3456, height: 4608 }, { width: null, height: null })
    ).toBe(false)
  })

  test('a downscaled thumbnail is not flagged even for portrait captures', () => {
    // Thumbnails keep raw orientation and different absolute dimensions, so
    // the exact-swap check does not fire.
    expect(
      isTransposed({ width: 1920, height: 2560 }, { width: 3456, height: 4608 })
    ).toBe(false)
  })
})
