import classNames from 'classnames'
import { DeterminationScore } from 'components/determination-score'
import { useCaptureMatches } from 'data-services/hooks/occurrences/useCaptureMatches'
import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { useOccurrencePath } from 'data-services/hooks/occurrences/useOccurrencePath'
import { CaptureDetection } from 'data-services/models/capture'
import { CaptureMatch } from 'data-services/models/capture-match'
import { PathFrame } from 'data-services/models/occurrence-path'
import _ from 'lodash'
import { Dialog, LoadingSpinner, Popover, Tooltip } from 'nova-ui-kit'
import {
  OccurrenceDetails,
  TABS,
} from 'pages/occurrence-details/occurrence-details'
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import {
  ReactZoomPanPinchRef,
  TransformComponent,
  TransformWrapper,
} from 'react-zoom-pan-pinch'
import { SCORE_THRESHOLDS } from 'utils/constants'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'
import { useActiveOccurrences } from '../hooks/useActiveOccurrences'
import { getNearestPathFrame } from './track-navigation'
import { useActiveCaptureId } from '../hooks/useActiveCapture'
import { useActiveDetection } from '../hooks/useActiveDetection'
import { BoxStyle, bboxToPercentStyle } from './bbox'
import { CaptureGhostTrail } from './capture-ghost-trail'
import { getMatchBoxStyle, getMatchLevel, isIdentified } from './capture-match'
import { CaptureMatchTooltip } from './capture-match-tooltip'
import { TierSources } from './capture-tiers'
import { ExtendClick, getExtendClickHint } from './extend-click'
import { ExtendTrackDialog, ExtendTrackState } from './extend-track'
import { buildTrail } from './ghost-trail'
import { OccurrenceToolbar } from './occurrence-toolbar'
import {
  SessionPathStatus,
  SessionTrackEdit,
  SessionTrackEdits,
} from './session-track-edits'
import styles from './capture.module.scss'
import { useCapturePreload } from './useCapturePreload'
import { useCaptureTiers } from './useCaptureTiers'

const FALLBACK_RATIO = 16 / 9

// react-zoom-pan-pinch's default maxScale; raised dynamically so large
// originals can always be inspected past 100% of their native pixels.
const DEFAULT_MAX_SCALE = 8
const MAX_OVERZOOM = 2

// Long enough for the pointer to cross the gap from a box to the panel under it.
const HOVER_CLOSE_DELAY_MS = 120

interface CaptureProps {
  captureDate?: Date
  captureId?: string
  defaultFilters: boolean
  detections: CaptureDetection[]
  extend: ExtendTrackState
  height: number | null
  onTogglePathCrops?: () => void
  showDetections?: boolean
  showPathCrops?: boolean
  sources?: TierSources
  transformRef: React.RefObject<ReactZoomPanPinchRef>
  width: number | null
}

export const Capture = ({
  captureDate,
  captureId,
  defaultFilters,
  detections,
  extend,
  height,
  onTogglePathCrops,
  showDetections,
  showPathCrops,
  sources,
  transformRef,
  width,
}: CaptureProps) => {
  const { activeOccurrences, setActiveOccurrences } = useActiveOccurrences()
  const { setActiveCaptureId } = useActiveCaptureId()
  const { activeDetectionId } = useActiveDetection()
  // A link can point at a detection rather than an occurrence, because regrouping moves
  // a detection between occurrences while the detection's own id never changes. Follow
  // one and it selects whichever track holds that detection now, which is the thing the
  // reader needs to see: where it ended up.
  const linkedOccurrenceId = activeDetectionId
    ? detections.find((detection) => detection.id === activeDetectionId)
        ?.occurrenceId
    : undefined

  useEffect(() => {
    if (!linkedOccurrenceId || activeOccurrences.includes(linkedOccurrenceId)) {
      return
    }

    setActiveOccurrences([...activeOccurrences, linkedOccurrenceId])
  }, [linkedOccurrenceId, activeOccurrences, setActiveOccurrences])

  // Which occurrence the operator asked to see the path of. Kept while that
  // occurrence stays selected, so stepping between captures redraws the same path.
  const [pathOccurrenceId, setPathOccurrenceId] = useState<string>()
  const shownPathId =
    pathOccurrenceId && activeOccurrences.includes(pathOccurrenceId)
      ? pathOccurrenceId
      : undefined
  const {
    path,
    isLoading: pathLoading,
    isFetching: pathFetching,
    error: pathError,
    refetch: refetchPath,
  } = useOccurrencePath(shownPathId, !!shownPathId)
  const isLoadingPath = pathLoading || pathFetching
  const { matches } = useCaptureMatches({
    captureId,
    enabled: !!extend.occurrenceId,
    occurrenceId: extend.occurrenceId,
  })

  // Set while extending, holding the path shown before it started, so ending extend
  // mode does not leave behind a path nobody asked for.
  const pathBeforeExtend = useRef<{ occurrenceId?: string }>()

  useEffect(() => {
    // The occurrence being extended is the only one selected, with its path drawn,
    // so every capture stepped through shows where the track has reached and no
    // other selection competes with the match colours.
    if (!extend.occurrenceId) {
      if (pathBeforeExtend.current) {
        setPathOccurrenceId(pathBeforeExtend.current.occurrenceId)
        pathBeforeExtend.current = undefined
      }

      return
    }

    if (!pathBeforeExtend.current) {
      pathBeforeExtend.current = { occurrenceId: pathOccurrenceId }
    }

    setPathOccurrenceId(extend.occurrenceId)

    if (
      activeOccurrences.length !== 1 ||
      activeOccurrences[0] !== extend.occurrenceId
    ) {
      setActiveOccurrences([extend.occurrenceId])
    }
  }, [extend.occurrenceId, activeOccurrences, setActiveOccurrences])

  const nearestFrame = useMemo(
    () => (path?.length ? getNearestPathFrame(path, captureDate) : undefined),
    [path, captureDate]
  )

  const trail = useMemo(
    () => (path?.length ? buildTrail(path, captureId, captureDate) : undefined),
    [path, captureId, captureDate]
  )
  const wrapperRef = useRef<HTMLDivElement>(null)
  const [naturalSize, setNaturalSize] = useState<{
    width: number
    height: number
  }>()
  const [isLoading, setIsLoading] = useState<boolean>()
  const [renderOverlay, setRenderOverlay] = useState<boolean>()
  const [containerWidth, setContainerWidth] = useState(0)
  const [scale, setScale] = useState(1)

  const {
    displayed,
    incoming,
    incomingLoaded,
    updateDemand,
    onIncomingLoad,
    onIncomingError,
  } = useCaptureTiers({ sources, captureWidth: width, captureHeight: height })

  const dpr = window.devicePixelRatio || 1

  // The container width drives both the tier demand and the zoom readout.
  useLayoutEffect(() => {
    const element = wrapperRef.current
    if (!element) {
      return
    }
    const measure = () =>
      setContainerWidth(element.getBoundingClientRect().width)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const demand = containerWidth * dpr * scale

  useEffect(() => {
    if (containerWidth) {
      updateDemand(demand)
    }
  }, [containerWidth, demand, updateDemand])

  useEffect(() => {
    // Show the spinner whenever the active capture changes; the previous
    // image stays visible underneath until the new tier loads.
    setIsLoading(true)
    setNaturalSize(undefined)
  }, [sources?.original])

  useCapturePreload({
    captureId,
    demand,
    enabled: isLoading === false && !!displayed,
  })

  useLayoutEffect(() => {
    // Ugly hack to make overlay correct on first render
    setRenderOverlay(true)
  }, [])

  const boxStyles = useMemo(
    () =>
      detections.reduce((result: { [key: string]: BoxStyle }, detection) => {
        const style = bboxToPercentStyle(detection.bbox, width, height)

        if (style) {
          result[detection.id] = style
        }

        return result
      }, {}),
    [width, height, detections]
  )

  const ratio = useMemo(() => {
    // Stored dimensions first: they match the detection box space and stay
    // constant across tiers, so the layout never shifts on a tier swap.
    if (width && height) {
      return width / height
    }

    if (naturalSize) {
      return naturalSize.width / naturalSize.height
    }

    return FALLBACK_RATIO
  }, [width, height, naturalSize])

  const maxScale = useMemo(() => {
    if (width && containerWidth) {
      const fullResolutionScale = width / (containerWidth * dpr)
      return Math.max(DEFAULT_MAX_SCALE, fullResolutionScale * MAX_OVERZOOM)
    }

    return DEFAULT_MAX_SCALE
  }, [width, containerWidth, dpr])

  // Zoom level relative to the original image's pixels: 100% = one image
  // pixel per device pixel.
  const zoomPercent = useMemo(() => {
    if (!width || !containerWidth) {
      return null
    }

    return Math.round(((containerWidth * dpr * scale) / width) * 100)
  }, [width, containerWidth, dpr, scale])

  return (
    <div
      className="relative w-full"
      ref={wrapperRef}
      style={{ aspectRatio: ratio }}
    >
      <TransformWrapper
        maxScale={maxScale}
        onTransform={(_, state) => setScale(state.scale)}
        ref={transformRef}
      >
        <TransformComponent
          contentClass="!w-full !h-full"
          wrapperClass="!w-full !h-full"
        >
          <img
            alt=""
            className="w-full h-full"
            src={displayed?.src}
            onLoad={(event) => {
              const image = event.currentTarget
              if (image.naturalWidth && image.naturalHeight) {
                setNaturalSize({
                  width: image.naturalWidth,
                  height: image.naturalHeight,
                })
              }
              setIsLoading(false)
            }}
            onError={() => {
              setNaturalSize(undefined)
              setIsLoading(false)
            }}
          />
          {incoming ? (
            <img
              alt=""
              key={incoming.src}
              className={classNames(
                'absolute inset-0 w-full h-full transition-opacity duration-300',
                incomingLoaded ? 'opacity-100' : 'opacity-0'
              )}
              src={incoming.src}
              onLoad={(event) => onIncomingLoad(event.currentTarget)}
              onError={onIncomingError}
            />
          ) : null}
          <div
            className={classNames(styles.details, {
              [styles.showOverlay]: showDetections && detections.length,
            })}
          >
            {renderOverlay ? <CaptureOverlay boxStyles={boxStyles} /> : null}
            {trail ? (
              <CaptureGhostTrail
                onSelectFrame={setActiveCaptureId}
                showCrops={showPathCrops}
                trail={trail}
              />
            ) : null}
            <CaptureDetections
              boxStyles={boxStyles}
              onTogglePathCrops={onTogglePathCrops}
              showPathCrops={showPathCrops}
              defaultFilters={defaultFilters}
              detections={detections}
              extend={extend}
              isLoadingPath={isLoadingPath}
              matches={matches}
              onHidePath={() => setPathOccurrenceId(undefined)}
              onShowPath={(occurrenceId) =>
                occurrenceId === shownPathId
                  ? refetchPath()
                  : setPathOccurrenceId(occurrenceId)
              }
              path={path}
              pathError={!!pathError}
              pathOccurrenceId={shownPathId}
              shownFrames={trail?.shownCount}
              showDetections={showDetections}
            />
          </div>
        </TransformComponent>
      </TransformWrapper>
      {shownPathId && !extend.occurrenceId ? (
        <SessionPathStatus
          error={!!pathError}
          isLoading={isLoadingPath}
          occurrenceId={shownPathId}
          onDismiss={() => setPathOccurrenceId(undefined)}
          onShowFrame={
            nearestFrame
              ? () => setActiveCaptureId(nearestFrame.captureId)
              : undefined
          }
        />
      ) : null}
      {extend.occurrenceId && extend.choice ? (
        <ExtendTrackDialog
          choice={extend.choice}
          extend={extend}
          occurrenceId={extend.occurrenceId}
        />
      ) : null}
      {zoomPercent !== null ? (
        <span className="absolute bottom-2 left-2 px-2.5 py-1 rounded-full bg-neutral-900/70 text-generic-white text-xs tabular-nums pointer-events-none select-none">
          {zoomPercent}%
        </span>
      ) : null}
      {incoming && !incomingLoaded ? (
        <span
          className="absolute bottom-2 right-2 flex items-center gap-2 px-2.5 py-1 rounded-full bg-neutral-900/70 text-generic-white text-xs pointer-events-none select-none"
          role="status"
        >
          <LoadingSpinner size={12} />
          <span>{translate(STRING.LOADING_HIGHER_RESOLUTION)}...</span>
        </span>
      ) : null}
      {isLoading ? (
        <div className="absolute inset-0 flex items-center justify-center">
          <LoadingSpinner />
        </div>
      ) : null}
    </div>
  )
}

const CaptureOverlay = ({
  boxStyles,
}: {
  boxStyles: { [key: number]: BoxStyle }
}) => (
  <svg className={styles.overlay}>
    <defs>
      <mask id="holes">
        <rect width="100%" height="100%" fill="white" />
        {Object.entries(boxStyles).map(([id, style]) => (
          <rect
            key={id}
            x={style.left}
            y={style.top}
            width={style.width}
            height={style.height}
            fill="black"
          />
        ))}
      </mask>
    </defs>
    <rect
      fill="black"
      fillOpacity={0.2}
      width="100%"
      height="100%"
      mask="url(#holes)"
    />
  </svg>
)

/**
 * What a screen reader hears on a detection box. In extend mode it also carries the
 * match reading and what activating the box does, which the pointer gets from the
 * preview card and a keyboard never sees.
 */
const getBoxLabel = ({
  click,
  detection,
  isExtending,
  match,
}: {
  click?: ExtendClick
  detection: CaptureDetection
  isExtending: boolean
  match?: CaptureMatch
}) => {
  const name = isIdentified(detection)
    ? translate(
        detection.score === 1
          ? STRING.TRACK_BOX_LABEL_VERIFIED
          : STRING.TRACK_BOX_LABEL,
        { name: detection.label, score: detection.scoreLabel as string }
      )
    : translate(STRING.TRACK_FRAME_DETECTION, { id: detection.id })

  if (!isExtending) {
    return name
  }

  const likelihood = match?.likelihood ?? null
  const label = translate(STRING.TRACK_BOX_EXTEND_LABEL, {
    match:
      likelihood !== null
        ? translate(STRING.TRACK_MATCH_SCORE, {
            level: translate(getMatchLevel(likelihood)),
            percent: Math.round(likelihood * 100),
          })
        : translate(STRING.VALUE_NOT_AVAILABLE),
    name,
  })
  const hint = click ? getExtendClickHint(click) : undefined

  return hint
    ? translate(STRING.TRACK_BOX_EXTEND_ACTION, {
        action: translate(hint.string),
        label,
      })
    : label
}

const CaptureDetections = ({
  boxStyles,
  defaultFilters,
  detections,
  extend,
  isLoadingPath,
  matches,
  onHidePath,
  onShowPath,
  onTogglePathCrops,
  path,
  pathError,
  pathOccurrenceId,
  showDetections,
  showPathCrops,
  shownFrames,
}: {
  boxStyles: { [key: number]: BoxStyle }
  defaultFilters: boolean
  detections: CaptureDetection[]
  extend: ExtendTrackState
  isLoadingPath?: boolean
  matches?: Record<string, CaptureMatch>
  onHidePath: () => void
  onShowPath: (occurrenceId: string) => void
  /** Switch the path's boxes between the moth's own pixels and an outline. */
  onTogglePathCrops?: () => void
  path?: PathFrame[]
  pathError?: boolean
  pathOccurrenceId?: string
  showDetections?: boolean
  /** The path's boxes are filled with each frame's crop rather than left empty. */
  showPathCrops?: boolean
  shownFrames?: number
}) => {
  // Held in state, not a ref: Radix needs the element itself to keep a panel inside
  // the image, and a ref assignment does not re-render to hand it over.
  const [container, setContainer] = useState<HTMLDivElement | null>(null)
  const [activeOccurrence, setActiveOccurrence] = useState<string>()
  const [trackEdit, setTrackEdit] = useState<SessionTrackEdit>()
  // Selected occurrences whose panel was closed with Escape; they stay selected.
  const [dismissedToolbars, setDismissedToolbars] = useState<string[]>([])
  const [hoveredBox, setHoveredBox] = useState<string>()
  const hoverTimeout = useRef<number>()
  const { activeOccurrences, setActiveOccurrences } = useActiveOccurrences()
  const isExtending = !!extend.occurrenceId
  const detailsHidden = isExtending && !extend.showDetails

  useEffect(() => {
    setDismissedToolbars([])
  }, [extend.showDetails])

  useEffect(() => {
    setHoveredBox(undefined)
  }, [detailsHidden])

  useEffect(() => () => window.clearTimeout(hoverTimeout.current), [])

  const hoverBox = (detectionId: string) => {
    window.clearTimeout(hoverTimeout.current)
    setHoveredBox(detectionId)
  }

  const unhoverBox = (detectionId: string) => {
    window.clearTimeout(hoverTimeout.current)
    hoverTimeout.current = window.setTimeout(
      () => setHoveredBox((box) => (box === detectionId ? undefined : box)),
      HOVER_CLOSE_DELAY_MS
    )
  }

  /** How a box is drawn, and whether the panel anchored to it is on screen. */
  const describeBox = (detection: CaptureDetection) => {
    const isExtended =
      !!detection.occurrenceId && detection.occurrenceId === extend.occurrenceId
    const isActive =
      isExtended ||
      (detection.occurrenceId
        ? activeOccurrences.includes(detection.occurrenceId)
        : false)
    const isDismissed =
      !!detection.occurrenceId &&
      dismissedToolbars.includes(detection.occurrenceId)
    // A selected box keeps its panel; any other box borrows it while hovered.
    const hasPanel =
      !detailsHidden && !!detection.occurrenceId && (showDetections || isActive)

    return {
      isActive,
      isDismissed,
      isExtended,
      panelOpen:
        hasPanel && (isActive ? !isDismissed : hoveredBox === detection.id),
    }
  }

  // Escape closes the innermost thing on screen: a dialog, then an open panel, then
  // extend mode. It never changes which occurrences are selected.
  const escapeHandledElsewhere =
    !!trackEdit ||
    !!activeOccurrence ||
    !!extend.choice ||
    detections.some((detection) => describeBox(detection).panelOpen)

  useEffect(() => {
    if (!isExtending || escapeHandledElsewhere) {
      return
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        extend.stop()
      }
    }

    document.addEventListener('keydown', onKeyDown)

    return () => document.removeEventListener('keydown', onKeyDown)
  }, [escapeHandledElsewhere, extend, isExtending])

  // Worded while the path is still the one on screen: the split moves the boundary
  // frame off this occurrence, so the refreshed path can no longer describe it.
  const describeSplit = (detectionId: string) => {
    const index =
      path?.findIndex((frame) => frame.detectionId === detectionId) ?? -1
    const timestamp = index >= 0 ? path?.[index].timestamp : undefined

    return {
      movedBySplit: path && index >= 0 ? path.length - index : 0,
      timeLabel: timestamp
        ? getFormatedTimeString({ date: timestamp, options: { second: true } })
        : translate(STRING.VALUE_NOT_AVAILABLE),
      total: path?.length ?? 0,
    }
  }

  const setDismissed = (occurrenceId: string, dismissed: boolean) =>
    setDismissedToolbars((ids) => [
      ...ids.filter((id) => id !== occurrenceId),
      ...(dismissed ? [occurrenceId] : []),
    ])

  const toggleActiveState = (occurrenceId: string) => {
    const isActive = activeOccurrences.includes(occurrenceId)
    setDismissed(occurrenceId, false)

    if (isActive) {
      setActiveOccurrences(
        activeOccurrences.filter((occurrence) => occurrence !== occurrenceId)
      )
    } else {
      setActiveOccurrences([...activeOccurrences, occurrenceId])
    }
  }

  // A path is only fetched for a selected occurrence, so asking for one from a
  // hovered box selects it first.
  const showPath = (occurrenceId: string) => {
    if (!activeOccurrences.includes(occurrenceId)) {
      setActiveOccurrences([...activeOccurrences, occurrenceId])
    }
    onShowPath(occurrenceId)
  }

  return (
    <>
      <div className={styles.detections} ref={setContainer}>
        {Object.entries(boxStyles).map(([id, style]) => {
          const detection = detections.find((d) => d.id === id)

          if (!detection) {
            return null
          }

          const { isActive, isDismissed, isExtended, panelOpen } =
            describeBox(detection)

          if (!showDetections && !isActive) {
            return null
          }

          const isClickable = !!detection.occurrenceId || isExtending
          const match = matches?.[detection.id]
          const click = isExtending ? extend.previewClick(detection) : undefined
          const box = (
            <button
              aria-label={getBoxLabel({ click, detection, isExtending, match })}
              aria-pressed={
                !isExtending && detection.occurrenceId ? isActive : undefined
              }
              className={classNames(styles.detection, {
                [styles.active]: isExtending ? isExtended : isActive,
                [styles.extended]: isExtended,
                [styles.filtered]:
                  !isExtending &&
                  defaultFilters &&
                  !detection.occurrenceMeetsCriteria,
                [styles.alert]:
                  !isExtending && detection.score < SCORE_THRESHOLDS.ALERT,
                [styles.warning]:
                  !isExtending && detection.score < SCORE_THRESHOLDS.WARNING,
                [styles.clickable]: isClickable,
              })}
              onClick={() => {
                if (extend.occurrenceId) {
                  extend.clickBox(detection)
                } else if (isActive && isDismissed) {
                  setDismissed(detection.occurrenceId as string, false)
                } else if (detection.occurrenceId) {
                  toggleActiveState(detection.occurrenceId)
                }
              }}
              onMouseEnter={() => hoverBox(detection.id)}
              onMouseLeave={() => unhoverBox(detection.id)}
              style={
                isExtending && !isExtended
                  ? { ...style, ...getMatchBoxStyle(match) }
                  : style
              }
              // A box a click does nothing to is read where it sits, not tabbed to.
              tabIndex={isClickable ? 0 : -1}
              type="button"
            />
          )

          // A reading of the box, which a tooltip is the right primitive for: Radix
          // repeats it for assistive technology, and text survives being read twice.
          if (detailsHidden || !detection.occurrenceId) {
            return (
              <Tooltip.Provider
                delayDuration={0}
                disableHoverableContent
                key={detection.id}
              >
                <Tooltip.Root open={hoveredBox === detection.id}>
                  <Tooltip.Trigger asChild>{box}</Tooltip.Trigger>
                  <Tooltip.Content
                    className={classNames(
                      'z-[1] pointer-events-none',
                      detailsHidden ? 'px-3 py-2' : 'p-3'
                    )}
                    collisionBoundary={container}
                    collisionPadding={8}
                    side="bottom"
                  >
                    {detailsHidden ? (
                      <CaptureMatchTooltip
                        click={click}
                        detection={detection}
                        detections={detections}
                        isTrackFrame={isExtended}
                        match={match}
                      />
                    ) : (
                      <div className="flex flex-col items-start gap-1">
                        <span className="body-base font-medium">
                          {detection.label}
                        </span>
                        <DeterminationScore
                          score={detection.score}
                          scoreLabel={detection.scoreLabel}
                          verified={detection.score === 1}
                        />
                      </div>
                    )}
                  </Tooltip.Content>
                </Tooltip.Root>
              </Tooltip.Provider>
            )
          }

          return (
            <Popover.Root key={detection.id} open={panelOpen}>
              <Popover.Trigger asChild>{box}</Popover.Trigger>
              <Popover.Content
                align="center"
                // The layer holding the boxes is transparent to the pointer so a path
                // frame below it stays reachable, so this panel, which has links in
                // it, has to take clicks back.
                className="w-auto p-3 z-[1] body-small pointer-events-auto"
                collisionBoundary={container}
                collisionPadding={8}
                onEscapeKeyDown={() => {
                  if (isActive) {
                    setDismissed(detection.occurrenceId as string, true)
                  } else {
                    setHoveredBox(undefined)
                  }
                }}
                onMouseEnter={() => hoverBox(detection.id)}
                onMouseLeave={() => unhoverBox(detection.id)}
                // The panel follows a selection or a hover rather than a deliberate
                // open, so it must not pull focus off the capture.
                onOpenAutoFocus={(event) => event.preventDefault()}
                side="bottom"
              >
                <OccurrenceToolbar
                  detectionId={detection.id}
                  isExtended={isExtended}
                  isLoadingPath={
                    isLoadingPath && pathOccurrenceId === detection.occurrenceId
                  }
                  occurrence={{
                    frameCount: detection.frameCount,
                    groupingVerified: detection.groupingVerified,
                    groupingVerifiedAt: detection.groupingVerifiedAt,
                    groupingVerifiedBy: detection.groupingVerifiedBy,
                    id: detection.occurrenceId,
                    label: detection.label,
                    score: detection.score,
                    scoreLabel: detection.scoreLabel,
                  }}
                  onExtend={() =>
                    extend.start(detection.occurrenceId as string)
                  }
                  onDismiss={() =>
                    setDismissed(detection.occurrenceId as string, true)
                  }
                  onHidePath={onHidePath}
                  onTogglePathCrops={onTogglePathCrops}
                  showPathCrops={showPathCrops}
                  onMerge={() =>
                    setTrackEdit({
                      action: 'merge',
                      detectionId: detection.id,
                      occurrenceId: detection.occurrenceId as string,
                    })
                  }
                  onOpenOccurrence={() =>
                    setActiveOccurrence(detection.occurrenceId)
                  }
                  onShowPath={() => showPath(detection.occurrenceId as string)}
                  onSplit={() =>
                    setTrackEdit({
                      action: 'split',
                      detectionId: detection.id,
                      occurrenceId: detection.occurrenceId as string,
                      ...describeSplit(detection.id),
                    })
                  }
                  onVerify={() =>
                    setTrackEdit({
                      action: 'verify',
                      detectionId: detection.id,
                      occurrenceId: detection.occurrenceId as string,
                      verified: detection.groupingVerified,
                    })
                  }
                  path={
                    pathOccurrenceId === detection.occurrenceId
                      ? path
                      : undefined
                  }
                  pathError={
                    pathError && pathOccurrenceId === detection.occurrenceId
                  }
                  shownFrames={
                    pathOccurrenceId === detection.occurrenceId
                      ? shownFrames
                      : undefined
                  }
                />
              </Popover.Content>
            </Popover.Root>
          )
        })}
        {activeOccurrence ? (
          <OccurrenceDetailsDialog
            id={activeOccurrence}
            onClose={() => setActiveOccurrence(undefined)}
          />
        ) : null}
        <SessionTrackEdits
          edit={trackEdit}
          onClose={() => setTrackEdit(undefined)}
        />
      </div>
    </>
  )
}

const OccurrenceDetailsDialog = ({
  id,
  onClose,
}: {
  id: string
  onClose: () => void
}) => {
  const [selectedView, setSelectedView] = useState<string | undefined>(
    TABS.FIELDS
  )
  const { occurrence, isLoading, error } = useOccurrenceDetails(id)
  const detailsLabel = translate(STRING.ENTITY_DETAILS, {
    type: _.capitalize(translate(STRING.ENTITY_TYPE_OCCURRENCE)),
  })

  return (
    <Dialog.Root
      open={!!id}
      onOpenChange={(open) => {
        if (!open) {
          onClose()
        }
      }}
    >
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
        error={error}
      >
        <div className="sr-only">
          <Dialog.Header title={occurrence?.displayName ?? detailsLabel}>
            <Dialog.Description>{detailsLabel}</Dialog.Description>
          </Dialog.Header>
        </div>
        {occurrence ? (
          <OccurrenceDetails
            occurrence={occurrence}
            onNavigate={onClose}
            selectedTab={selectedView}
            setSelectedTab={setSelectedView}
          />
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
