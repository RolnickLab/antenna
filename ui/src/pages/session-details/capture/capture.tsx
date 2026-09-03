import classNames from 'classnames'
import { DeterminationScore } from 'components/determination-score'
import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { CaptureDetection } from 'data-services/models/capture'
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
import { STRING, translate } from 'utils/language'
import { useActiveOccurrences } from '../hooks/useActiveOccurrences'
import { TierSources } from './capture-tiers'
import styles from './capture.module.scss'
import { useCaptureTiers } from './useCaptureTiers'

const FALLBACK_RATIO = 16 / 9

// react-zoom-pan-pinch's default maxScale; raised dynamically so large
// originals can always be inspected past 100% of their native pixels.
const DEFAULT_MAX_SCALE = 8
const MAX_OVERZOOM = 2

interface BoxStyle {
  width: string
  height: string
  top: string
  left: string
}

interface CaptureProps {
  defaultFilters: boolean
  detections: CaptureDetection[]
  height: number | null
  showDetections?: boolean
  sources?: TierSources
  transformRef: React.RefObject<ReactZoomPanPinchRef>
  width: number | null
}

export const Capture = ({
  defaultFilters,
  detections,
  height,
  showDetections,
  sources,
  transformRef,
  width,
}: CaptureProps) => {
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
        const [boxLeft, boxTop, boxRight, boxBottom] = detection.bbox
        const boxWidth = boxRight - boxLeft
        const boxHeight = boxBottom - boxTop

        // Boxes are in the original image's pixel space and the rendered image
        // may be a downscaled thumbnail, so only stored dimensions can scale them.
        if (!width || !height) {
          return result
        }

        result[detection.id] = {
          width: `${(boxWidth / width) * 100}%`,
          height: `${(boxHeight / height) * 100}%`,
          top: `${(boxTop / height) * 100}%`,
          left: `${(boxLeft / width) * 100}%`,
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
            <CaptureDetections
              boxStyles={boxStyles}
              defaultFilters={defaultFilters}
              detections={detections}
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
  defaultFilters,
  detections,
  showDetections,
}: {
  boxStyles: { [key: number]: BoxStyle }
  defaultFilters: boolean
  detections: CaptureDetection[]
  showDetections?: boolean
}) => {
  const containerRef = useRef(null)
  const [activeOccurrence, setActiveOccurrence] = useState<string>()
  const { activeOccurrences, setActiveOccurrences } = useActiveOccurrences()

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
                  <div className="flex flex-col items-start gap-1">
                    <button
                      className="body-base text-primary font-medium"
                      disabled={!detection.occurrenceId}
                      onClick={() =>
                        setActiveOccurrence(detection.occurrenceId)
                      }
                    >
                      <span>{detection.label}</span>
                    </button>
                    <DeterminationScore
                      score={detection.score}
                      scoreLabel={detection.scoreLabel}
                      verified={detection.score === 1}
                    />
                  </div>
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
