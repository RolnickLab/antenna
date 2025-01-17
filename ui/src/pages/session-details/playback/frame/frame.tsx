import classNames from 'classnames'
import { CaptureDetection } from 'data-services/models/capture'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES, SCORE_THRESHOLDS } from 'utils/constants'
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
}

export const Frame = ({
  src,
  width,
  height,
  detections,
  showDetections,
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
}: {
  boxStyles: { [key: number]: BoxStyle }
  detections: CaptureDetection[]
  showDetections?: boolean
}) => {
  const { projectId } = useParams()
  const containerRef = useRef(null)
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
          <Tooltip
            key={detection.id}
            content={detection?.label ?? ''}
            frame={containerRef.current}
            open={isActive ? isActive : undefined}
            to={
              detection.occurrenceId
                ? APP_ROUTES.OCCURRENCE_DETAILS({
                    projectId: projectId as string,
                    occurrenceId: detection.occurrenceId,
                  })
                : undefined
            }
          >
            <div
              style={style}
              className={classNames(styles.detection, {
                [styles.active]: isActive,
                [styles.warning]: detection.score < SCORE_THRESHOLDS.WARNING,
                [styles.alert]: detection.score < SCORE_THRESHOLDS.ALERT,
                [styles.clickable]: !!detection.occurrenceId,
              })}
              onClick={() => {
                if (detection.occurrenceId) {
                  toggleActiveState(detection?.occurrenceId)
                }
              }}
            />
          </Tooltip>
        )
      })}
    </div>
  )
}
