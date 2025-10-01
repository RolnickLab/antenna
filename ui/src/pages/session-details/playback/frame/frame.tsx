import classNames from 'classnames'
import { useOccurrenceDetails } from 'data-services/hooks/occurrences/useOccurrenceDetails'
import { CaptureDetection } from 'data-services/models/capture'
import * as Dialog from 'design-system/components/dialog/dialog'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { InfoIcon } from 'lucide-react'
import { Button, Tooltip } from 'nova-ui-kit'
import {
  OccurrenceDetails,
  TABS,
} from 'pages/occurrence-details/occurrence-details'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { getScoreColorClass } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { useActiveOccurrences } from '../useActiveOccurrences'
import styles from './frame.module.scss'
import { BoxStyle } from './types'

const FALLBACK_RATIO = 16 / 9

interface FrameProps {
  src?: string
  width: number | null
  height: number | null
  detections: CaptureDetection[]
  showDetections?: boolean
  projectScoreThreshold?: number
}

export const Frame = ({
  src,
  width,
  height,
  detections,
  showDetections,
  projectScoreThreshold,
}: FrameProps) => {
  const [naturalSize, setNaturalSize] = useState<{
    width: number
    height: number
  }>()
  const imageRef = useRef<HTMLImageElement>(null)
  const [isLoading, setIsLoading] = useState<boolean>()
  const [renderOverlay, setRenderOverlay] = useState<boolean>()

  useLayoutEffect(() => {
    if (!imageRef.current) {
      return
    }

    setIsLoading(true)
    setNaturalSize(undefined)

    if (src) {
      imageRef.current.src = src
      imageRef.current.onload = () => {
        if (imageRef.current?.width && imageRef.current.height) {
          setNaturalSize({
            width: imageRef.current.naturalWidth,
            height: imageRef.current.naturalHeight,
          })
        }
        setIsLoading(false)
      }

      imageRef.current.onerror = () => {
        setNaturalSize(undefined)
        setIsLoading(false)
      }
    }
  }, [src])

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

        const _width = naturalSize?.width ?? width
        const _height = naturalSize?.height ?? height

        if (!_width || !_height) {
          return result
        }

        result[detection.id] = {
          width: `${(boxWidth / _width) * 100}%`,
          height: `${(boxHeight / _height) * 100}%`,
          top: `${(boxTop / _height) * 100}%`,
          left: `${(boxLeft / _width) * 100}%`,
        }

        return result
      }, {}),
    [width, height, naturalSize, detections]
  )

  const ratio = useMemo(() => {
    if (naturalSize) {
      return naturalSize.width / naturalSize.height
    }

    if (width && height) {
      return width / height
    }

    return FALLBACK_RATIO
  }, [width, height, naturalSize])

  return (
    <div
      className={classNames(styles.wrapper)}
      style={{
        paddingBottom: `${(1 / ratio) * 100}%`,
      }}
    >
      <img ref={imageRef} className={styles.image} />
      <div
        className={classNames(styles.details, {
          [styles.showOverlay]: showDetections,
        })}
      >
        {renderOverlay && <FrameOverlay boxStyles={boxStyles} />}
        <FrameDetections
          boxStyles={boxStyles}
          detections={detections}
          showDetections={showDetections}
          projectScoreThreshold={projectScoreThreshold}
        />
      </div>
      {isLoading && (
        <div className={styles.loadingWrapper}>
          <LoadingSpinner />
        </div>
      )}
    </div>
  )
}

const FrameOverlay = ({
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

const FrameDetections = ({
  boxStyles,
  detections,
  showDetections,
  projectScoreThreshold,
}: {
  boxStyles: { [key: number]: BoxStyle }
  detections: CaptureDetection[]
  showDetections?: boolean
  projectScoreThreshold?: number
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
                      [styles[
                        getScoreColorClass(
                          detection.score,
                          projectScoreThreshold
                        )
                      ]]: true,
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
                  className="p-1 z-[1]"
                  collisionBoundary={containerRef?.current}
                  side="bottom"
                >
                  <div className="flex items-center gap-2">
                    <span className="pl-2 body-sm pt-0.5">
                      {detection.label}
                    </span>
                    <Button
                      className="h-8 w-8"
                      disabled={!detection.occurrenceId}
                      onClick={() =>
                        setActiveOccurrence(detection.occurrenceId)
                      }
                      size="icon"
                      variant="ghost"
                    >
                      <InfoIcon className="w-4 h-4" />
                    </Button>
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

export const OccurrenceDetailsDialog = ({
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
