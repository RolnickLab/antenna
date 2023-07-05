import {
  OccurrenceDetails,
  OccurrenceDetailsDetectionInfo,
} from 'data-services/models/occurrence-details'
import styles from './blueprint-detections.module.scss'

export const BlueprintDetections = ({
  occurrence,
}: {
  occurrence: OccurrenceDetails
}) => (
  <div className={styles.blueprint}>
    {occurrence.detections.map((id) => {
      const detection = occurrence.getDetectionInfo(id)

      return detection ? (
        <BlueprintDetection key={id} detection={detection} />
      ) : null
    })}
  </div>
)

const BlueprintDetection = ({
  detection,
}: {
  detection: OccurrenceDetailsDetectionInfo
}) => (
  <div className={styles.blueprintDetection}>
    <span
      className={styles.blueprintTimestamp}
      style={{ width: detection.image.width }}
    >
      {detection.timeLabel}
    </span>
    <div className={styles.blueprintImage}>
      <img
        src={detection.image.src}
        alt=""
        width={detection.image.width}
        height={detection.image.height}
      />
    </div>
    <span className={styles.blueprintLabel}>
      {detection.name} ({detection.score})
    </span>
  </div>
)
