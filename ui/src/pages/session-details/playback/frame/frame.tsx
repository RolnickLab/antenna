import classNames from 'classnames'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import React, { useCallback, useEffect, useRef, useState } from 'react'
import styles from './frame.module.scss'

interface FrameProps {
  src: string
  width: number
  height: number
  detections: { id: number; bbox: number[] }[]
}

export const Frame = ({ src, width, height, detections }: FrameProps) => {
  const imageRef = useRef<HTMLImageElement>(null)
  const [isLoading, setIsLoading] = useState<boolean>()

  useEffect(() => {
    if (!imageRef.current) {
      return
    }
    setIsLoading(true)
    imageRef.current.src = src
    imageRef.current.onload = () => setIsLoading(false)
  }, [src])

  const getBoxStyles = useCallback(
    (
      bbox: number[]
    ): { width: string; height: string; top: string; left: string } => {
      const [boxLeft, boxTop, boxRight, boxBottom] = bbox
      const boxWidth = boxRight - boxLeft
      const boxHeight = boxBottom - boxTop

      return {
        width: `${(boxWidth / width) * 100}%`,
        height: `${(boxHeight / height) * 100}%`,
        top: `${(boxTop / height) * 100}%`,
        left: `${(boxLeft / width) * 100}%`,
      }
    },
    [width, height]
  )

  return (
    <div
      className={classNames(styles.wrapper)}
      style={{ paddingBottom: `${(height / width) * 100}%` }}
    >
      <img ref={imageRef} className={styles.image} />
      <svg className={styles.overlay}>
        <defs>
          <mask id="holes">
            <rect width="100%" height="100%" fill="white" />
            {detections.map((detection) => {
              const boxStyles = getBoxStyles(detection.bbox)

              return (
                <rect
                  key={detection.id}
                  x={boxStyles.left}
                  y={boxStyles.top}
                  width={boxStyles.width}
                  height={boxStyles.height}
                  fill="black"
                />
              )
            })}
          </mask>
        </defs>
        <rect fill="black" width="100%" height="100%" mask="url(#holes)" />
      </svg>
      {isLoading && (
        <div className={styles.loadingWrapper}>
          <LoadingSpinner />
        </div>
      )}
    </div>
  )
}
