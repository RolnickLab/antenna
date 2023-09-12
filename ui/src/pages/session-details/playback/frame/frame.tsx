import classNames from 'classnames'
import { CaptureDetection } from 'data-services/models/capture'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { useActiveOccurrences } from '../useActiveOccurrences'
import styles from './frame.module.scss'
import { BoxStyle } from './types'

interface FrameProps {
  src?: string
  width: number
  height: number
  detections: CaptureDetection[]
  showOverlay?: boolean
}

export const Frame = ({
  src,
  width,
  height,
  detections,
  showOverlay,
}: FrameProps) => {
  const imageRef = useRef<HTMLImageElement>(null)
  const [isLoading, setIsLoading] = useState<boolean>()
  const [rendeOverlay, setRenderOverlay] = useState<boolean>()

  useLayoutEffect(() => {
    if (!imageRef.current) {
      return
    }
    setIsLoading(true)
    if (src) {
      imageRef.current.src = src
      imageRef.current.onload = () => setIsLoading(false)
      imageRef.current.onerror = () => setIsLoading(false)
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

  return (
    <div
      className={classNames(styles.wrapper)}
      style={{ paddingBottom: `${(height / width) * 100}%` }}
    >
      <img ref={imageRef} className={styles.image} />
      <div
        className={classNames(styles.details, {
          [styles.showOverlay]: showOverlay,
        })}
      >
        {rendeOverlay && <FrameOverlay boxStyles={boxStyles} />}
        <FrameDetections detections={detections} boxStyles={boxStyles} />
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
  detections,
  boxStyles,
}: {
  detections: CaptureDetection[]
  boxStyles: { [key: number]: BoxStyle }
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

        if (!detection) {
          return null
        }

        const isActive = detection
          ? activeOccurrences.includes(detection.occurrenceId)
          : false

        return (
          <Tooltip
            key={detection.id}
            content={detection?.label ?? ''}
            frame={containerRef.current}
            open={isActive ? isActive : undefined}
            to={APP_ROUTES.OCCURRENCE_DETAILS({
              projectId: projectId as string,
              occurrenceId: detection.occurrenceId,
            })}
          >
            <div
              style={style}
              className={classNames(styles.detection, {
                [styles.active]: isActive,
              })}
              onClick={() => {
                if (detection) {
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
