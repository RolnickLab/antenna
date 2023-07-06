import classNames from 'classnames'
import { RefObject } from 'react'
import styles from './capture-row.module.scss'

export const CaptureRow = ({
  capture,
  innerRef,
  isActive,
  isEmpty,
  onClick,
}: {
  capture: {
    details: string
    scale: number
    timeLabel: string
  }
  innerRef?: RefObject<HTMLDivElement>
  isActive?: boolean
  isEmpty?: boolean
  onClick?: () => void
}) => (
  <div
    ref={innerRef}
    className={classNames(styles.capture, {
      [styles.active]: isActive,
      [styles.empty]: isEmpty,
    })}
    onClick={onClick}
  >
    <div className={styles.numDetections}>{capture.details}</div>
    <div className={styles.barContainer}>
      <div
        className={styles.bar}
        style={{
          width: `${capture.scale * 100}%`,
        }}
      />
    </div>
    <div className={styles.timestamp}>{capture.timeLabel}</div>
  </div>
)
