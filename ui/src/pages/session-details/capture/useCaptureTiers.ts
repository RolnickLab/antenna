import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  buildTierLadder,
  CaptureTier,
  isTransposed,
  pickTier,
  TierSources,
} from './capture-tiers'

/** Let a pinch/scroll gesture settle before any higher-tier fetch fires. */
const PROMOTE_DEBOUNCE_MS = 300

/** Keep in sync with the duration-300 class on the incoming image. */
const CROSSFADE_MS = 300

/**
 * Owns the resolution ladder state for the session detail capture: which tier
 * is displayed, which higher tier is loading, and the crossfade between them.
 *
 * The caller reports pixel demand (container width × devicePixelRatio × zoom
 * scale) via updateDemand; the hook debounces promotion so a zoom gesture
 * settles before a fetch fires. Tiers are only ever promoted — a downloaded
 * tier is never traded back for a blurrier one.
 */
export const useCaptureTiers = ({
  sources,
  captureWidth,
  captureHeight,
}: {
  sources?: TierSources
  captureWidth: number | null
  captureHeight: number | null
}) => {
  const [displayed, setDisplayed] = useState<CaptureTier | null>(null)
  const [incoming, setIncoming] = useState<CaptureTier | null>(null)
  const [incomingLoaded, setIncomingLoaded] = useState(false)

  const medium = sources?.medium
  const large = sources?.large
  const original = sources?.original

  const tiers = useMemo(
    () =>
      original
        ? buildTierLadder({ medium, large, original }, captureWidth)
        : [],
    [medium, large, original, captureWidth]
  )

  // Mirror state into refs so the debounce timer always acts on fresh values.
  const tiersRef = useRef(tiers)
  tiersRef.current = tiers
  const displayedRef = useRef(displayed)
  displayedRef.current = displayed
  const incomingRef = useRef(incoming)
  incomingRef.current = incoming
  const incomingLoadedRef = useRef(incomingLoaded)
  incomingLoadedRef.current = incomingLoaded
  const storedDimensionsRef = useRef({
    width: captureWidth,
    height: captureHeight,
  })
  storedDimensionsRef.current = { width: captureWidth, height: captureHeight }

  const demandRef = useRef(0)
  // Tiers that failed to load or turned out EXIF-rotated; skipped for the
  // rest of this capture's ladder so promotion does not retry in a loop.
  const unusableSrcsRef = useRef<Set<string>>(new Set())
  const promoteTimerRef = useRef<ReturnType<typeof setTimeout>>()
  const commitTimerRef = useRef<ReturnType<typeof setTimeout>>()

  const selectTier = useCallback((demand: number) => {
    const usable = tiersRef.current.filter(
      (tier) => !unusableSrcsRef.current.has(tier.src)
    )
    return pickTier(usable, demand)
  }, [])

  // Reset the ladder when navigating to another capture. While the capture is
  // loading (original undefined) the previous image stays displayed, matching
  // the pre-ladder behavior of keeping the old frame under the spinner.
  useEffect(() => {
    if (!original) {
      return
    }
    clearTimeout(promoteTimerRef.current)
    clearTimeout(commitTimerRef.current)
    unusableSrcsRef.current = new Set()
    setIncoming(null)
    setIncomingLoaded(false)
    // Demand is already known when navigating between captures; on first mount
    // it is 0 until the container is measured, and updateDemand picks the
    // initial tier as soon as the measurement arrives.
    setDisplayed(demandRef.current > 0 ? selectTier(demandRef.current) : null)
  }, [original, selectTier])

  const evaluatePromotion = useCallback(() => {
    const current = displayedRef.current
    const target = selectTier(demandRef.current)
    if (!current || !target) {
      return
    }

    const ladder = tiersRef.current
    const currentIndex = ladder.findIndex((tier) => tier.src === current.src)
    const targetIndex = ladder.findIndex((tier) => tier.src === target.src)

    if (targetIndex > currentIndex) {
      if (incomingRef.current?.src !== target.src) {
        clearTimeout(commitTimerRef.current)
        setIncoming(target)
        setIncomingLoaded(false)
      }
    } else if (incomingRef.current && !incomingLoadedRef.current) {
      // Zoomed back out before the upgrade arrived — drop the request. A tier
      // that already finished loading is committed regardless (never demote).
      setIncoming(null)
    }
  }, [selectTier])

  const updateDemand = useCallback(
    (demand: number) => {
      demandRef.current = demand

      if (!displayedRef.current) {
        const initial = selectTier(demand)
        if (initial) {
          setDisplayed(initial)
        }
        return
      }

      clearTimeout(promoteTimerRef.current)
      promoteTimerRef.current = setTimeout(
        evaluatePromotion,
        PROMOTE_DEBOUNCE_MS
      )
    },
    [evaluatePromotion, selectTier]
  )

  const onIncomingLoad = useCallback((image: HTMLImageElement) => {
    const tier = incomingRef.current
    if (!tier) {
      return
    }

    // A browser-applied EXIF rotation would misalign the detection boxes (the
    // bug PR #1374 fixed), so refuse the upgrade and stay on the current tier.
    if (
      isTransposed(
        { width: image.naturalWidth, height: image.naturalHeight },
        storedDimensionsRef.current
      )
    ) {
      unusableSrcsRef.current.add(tier.src)
      setIncoming(null)
      setIncomingLoaded(false)
      return
    }

    setIncomingLoaded(true)
    commitTimerRef.current = setTimeout(() => {
      setDisplayed(tier)
      setIncoming(null)
      setIncomingLoaded(false)
    }, CROSSFADE_MS + 50)
  }, [])

  const onIncomingError = useCallback(() => {
    const tier = incomingRef.current
    if (!tier) {
      return
    }
    unusableSrcsRef.current.add(tier.src)
    setIncoming(null)
    setIncomingLoaded(false)
  }, [])

  useEffect(
    () => () => {
      clearTimeout(promoteTimerRef.current)
      clearTimeout(commitTimerRef.current)
    },
    []
  )

  return {
    displayed,
    incoming,
    incomingLoaded,
    updateDemand,
    onIncomingLoad,
    onIncomingError,
  }
}
