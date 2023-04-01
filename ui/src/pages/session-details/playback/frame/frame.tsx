import React, { useCallback } from 'react'
import styles from './frame.module.scss'

export const Frame = ({
  src,
  width,
  height,
  detections,
}: {
  src: string
  width: number
  height: number
  detections: { id: number; bbox: number[] }[]
}) => {
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
      className={styles.wrapper}
      style={{ paddingBottom: `${(height / width) * 100}%` }}
    >
      <img src={src} className={styles.bg} />
      <div className={styles.overlay} />
      <img src={src} className={styles.detections} />
      <svg className={styles.svg}>
        <defs>
          <clipPath id="boxes">
            {detections.map((detection) => {
              const boxStyles = getBoxStyles(detection.bbox)

              return (
                <rect
                  key={detection.id}
                  x={boxStyles.left}
                  y={boxStyles.top}
                  width={boxStyles.width}
                  height={boxStyles.height}
                />
              )
            })}
          </clipPath>
        </defs>
      </svg>
    </div>
  )
}
