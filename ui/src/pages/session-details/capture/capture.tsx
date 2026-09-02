import classNames from 'classnames'
import { DeterminationScore } from 'components/determination-score'
import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { useOccurrencePath } from 'data-services/hooks/occurrences/useOccurrencePath'
import { CaptureDetection } from 'data-services/models/capture'
import { PathFrame } from 'data-services/models/occurrence-path'
import { Dialog, LoadingSpinner, Tooltip } from 'nova-ui-kit'
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
import { BoxStyle, bboxToPercentStyle } from './bbox'
import { buildTrail, CaptureGhostTrail } from './capture-ghost-trail'
import { TierSources } from './capture-tiers'
import { OccurrenceToolbar } from './occurrence-toolbar'
import { SessionTrackEdit, SessionTrackEdits } from './session-track-edits'
import styles from './capture.module.scss'
import { useCaptureTiers } from './useCaptureTiers'

const FALLBACK_RATIO = 16 / 9

// react-zoom-pan-pinch's default maxScale; raised dynamically so large
// originals can always be inspected past 100% of their native pixels.
const DEFAULT_MAX_SCALE = 8
const MAX_OVERZOOM = 2

interface CaptureProps {
  captureId?: string
  defaultFilters: boolean
  detections: CaptureDetection[]
  height: number | null
  showDetections?: boolean
  sources?: TierSources
  transformRef: React.RefObject<ReactZoomPanPinchRef>
  width: number | null
}

export const Capture = ({
  captureId,
  defaultFilters,
  detections,
  height,
  showDetections,
  sources,
  transformRef,
  width,
}: CaptureProps) => {
  const { activeOccurrences } = useActiveOccurrences()
  // Which occurrence the operator asked to see the path of. Kept while that
  // occurrence stays selected, so stepping between captures redraws the same path.
  const [pathOccurrenceId, setPathOccurrenceId] = useState<string>()
  const shownPathId =
    pathOccurrenceId && activeOccurrences.includes(pathOccurrenceId)
      ? pathOccurrenceId
      : undefined
  const { path, isLoading: isLoadingPath } = useOccurrencePath(
    shownPathId,
    !!shownPathId
  )
  const trail = useMemo(
    () => (path?.length ? buildTrail(path, captureId) : undefined),
    [path, captureId]
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

  useEffect(() => {
    if (containerWidth) {
      updateDemand(containerWidth * dpr * scale)
    }
  }, [containerWidth, dpr, scale, updateDemand])

  useEffect(() => {
    // Show the spinner whenever the active capture changes; the previous
    // image stays visible underneath until the new tier loads.
    setIsLoading(true)
    setNaturalSize(undefined)
  }, [sources?.original])

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
            {trail ? <CaptureGhostTrail trail={trail} /> : null}
            <CaptureDetections
              boxStyles={boxStyles}
              defaultFilters={defaultFilters}
              detections={detections}
              captureId={captureId}
              isLoadingPath={isLoadingPath}
              onHidePath={() => setPathOccurrenceId(undefined)}
              onShowPath={setPathOccurrenceId}
              path={path}
              pathOccurrenceId={shownPathId}
              shownFrames={trail?.shownCount}
              showDetections={showDetections}
            />
          </div>
        </TransformComponent>
      </TransformWrapper>
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

const CaptureDetections = ({
  boxStyles,
  captureId,
  defaultFilters,
  detections,
  isLoadingPath,
  onHidePath,
  onShowPath,
  path,
  pathOccurrenceId,
  showDetections,
  shownFrames,
}: {
  boxStyles: { [key: number]: BoxStyle }
  captureId?: string
  defaultFilters: boolean
  detections: CaptureDetection[]
  isLoadingPath?: boolean
  onHidePath: () => void
  onShowPath: (occurrenceId: string) => void
  path?: PathFrame[]
  pathOccurrenceId?: string
  showDetections?: boolean
  shownFrames?: number
}) => {
  const containerRef = useRef(null)
  const [activeOccurrence, setActiveOccurrence] = useState<string>()
  const [trackEdit, setTrackEdit] = useState<SessionTrackEdit>()
  const { activeOccurrences, setActiveOccurrences } = useActiveOccurrences()

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

  const toggleActiveState = (occurrenceId: string) => {
    const isActive = activeOccurrences.includes(occurrenceId)

    if (isActive) {
      setActiveOccurrences(
        activeOccurrences.filter((occurrence) => occurrence !== occurrenceId)
      )
    } else {
      setActiveOccurrences([...activeOccurrences, occurrenceId])
    }
  }

  return (
    <>
      <div className={styles.detections} ref={containerRef}>
        {Object.entries(boxStyles).map(([id, style]) => {
          const detection = detections.find((d) => d.id === id)

          const isActive = detection?.occurrenceId
            ? activeOccurrences.includes(detection.occurrenceId)
            : false

          if (!detection || (!showDetections && !isActive)) {
            return null
          }

          return (
            <Tooltip.Provider key={detection.id} delayDuration={0}>
              <Tooltip.Root open={isActive ? isActive : undefined}>
                <Tooltip.Trigger asChild>
                  <div
                    style={style}
                    className={classNames(styles.detection, {
                      [styles.active]: isActive,
                      [styles.filtered]: defaultFilters
                        ? !detection.occurrenceMeetsCriteria
                        : false,
                      [styles.alert]: detection.score < SCORE_THRESHOLDS.ALERT,
                      [styles.warning]:
                        detection.score < SCORE_THRESHOLDS.WARNING,
                      [styles.clickable]: !!detection.occurrenceId,
                    })}
                    onClick={() => {
                      if (detection.occurrenceId) {
                        toggleActiveState(detection?.occurrenceId)
                      }
                    }}
                  />
                </Tooltip.Trigger>
                <Tooltip.Content
                  className="p-3 z-[1]"
                  collisionBoundary={containerRef?.current}
                  side="bottom"
                >
                  {detection.occurrenceId ? (
                    <OccurrenceToolbar
                      isLoadingPath={
                        isLoadingPath &&
                        pathOccurrenceId === detection.occurrenceId
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
                      onHidePath={onHidePath}
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
                      onShowPath={() =>
                        onShowPath(detection.occurrenceId as string)
                      }
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
                      shownFrames={
                        pathOccurrenceId === detection.occurrenceId
                          ? shownFrames
                          : undefined
                      }
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
        })}
        {activeOccurrence ? (
          <OccurrenceDetailsDialog
            id={activeOccurrence}
            onClose={() => setActiveOccurrence(undefined)}
          />
        ) : null}
        <SessionTrackEdits
          captureId={captureId}
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
        {occurrence ? (
          <OccurrenceDetails
            occurrence={occurrence}
            selectedTab={selectedView}
            setSelectedTab={setSelectedView}
          />
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
