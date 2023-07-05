import classNames from 'classnames'
import { Capture } from 'data-services/models/capture'
import { RefObject } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './capture-row.module.scss'

export const CaptureRow = ({
  capture,
  innerRef,
  isActive,
  scale,
  onClick,
}: {
  capture: Capture
  innerRef: RefObject<HTMLDivElement>
  isActive: boolean
  scale: number
  onClick: () => void
}) => (
  <div
    ref={innerRef}
    key={capture.id}
    className={classNames(styles.capture, {
      [styles.active]: isActive,
      [styles.empty]: capture.numDetections === 0,
    })}
    onClick={onClick}
  >
    <div className={styles.numDetections}>
      {capture.numDetections} {translate(STRING.DETAILS_LABEL_DETECTIONS)}
    </div>
    <div className={styles.barContainer}>
      <div
        className={styles.bar}
        style={{
          width: `${scale * 100}%`,
        }}
      />
    </div>
    <div className={styles.timestamp}>{capture.timeLabel}</div>
  </div>
)
