import classNames from 'classnames'
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
  capture: any // TODO: Update when we have real data
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
      [styles.empty]: capture.num_detections === 0,
    })}
    onClick={onClick}
  >
    <div className={styles.numDetections}>
      {capture.num_detections} {translate(STRING.DETAILS_LABEL_DETECTIONS)}
    </div>
    <div className={styles.barContainer}>
      <div
        className={styles.bar}
        style={{
          width: `${scale * 100}%`,
        }}
      />
    </div>
    <div className={styles.timestamp}>
      {new Date(capture.timestamp).toLocaleTimeString()}
    </div>
  </div>
)
