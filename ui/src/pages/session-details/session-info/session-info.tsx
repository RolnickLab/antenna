import { Session } from 'data-services/models/session'
import { STRING, translate } from 'utils/language'
import styles from './session-info.module.scss'

export const SessionInfo = ({ session }: { session: Session }) => (
  <>
    <h1 className={styles.title}>
      {translate(STRING.SESSION)} {session.idLabel}
    </h1>
    <div className={styles.content}>
      <p className={styles.fieldGroup}>
        <span className={styles.fieldLabel}>
          {translate(STRING.DETAILS_LABEL_DEPLOYMENT)}
        </span>
        <span className={styles.fieldValue}>{session.deploymentLabel}</span>
      </p>
      <p className={styles.fieldGroup}>
        <span className={styles.fieldLabel}>
          {translate(STRING.DETAILS_LABEL_DATE)}
        </span>
        <span className={styles.fieldValue}>{session.datespanLabel}</span>
      </p>
      <p className={styles.fieldGroup}>
        <span className={styles.fieldLabel}>
          {translate(STRING.DETAILS_LABEL_TIME)}
        </span>
        <span className={styles.fieldValue}>{session.timespanLabel}</span>
      </p>
      <p className={styles.fieldGroup}>
        <span className={styles.fieldLabel}>
          {translate(STRING.DETAILS_LABEL_DURATION)}
        </span>
        <span className={styles.fieldValue}>{session.durationLabel}</span>
      </p>
      <p className={styles.fieldGroup}>
        <span className={styles.fieldLabel}>
          {translate(STRING.DETAILS_LABEL_ELEVATION)}
        </span>
        <span className={styles.fieldValue}>WIP</span>
      </p>

      <p className={styles.fieldGroup}>
        <span className={styles.fieldLabel}>
          {translate(STRING.DETAILS_LABEL_AVG_TEMP)}
        </span>
        <span className={styles.fieldValue}>WIP</span>
      </p>
      <p className={styles.fieldGroup}>
        <span className={styles.fieldLabel}>
          {translate(STRING.DETAILS_LABEL_AVG_WEATHER)}
        </span>
        <span className={styles.fieldValue}>WIP</span>
      </p>
      <p className={styles.fieldGroup}>
        <span className={styles.fieldLabel}>
          {translate(STRING.DETAILS_LABEL_LIGHT_SOURCE)}
        </span>
        <span className={styles.fieldValue}>WIP</span>
      </p>
      <p className={styles.fieldGroup}>
        <span className={styles.fieldLabel}>
          {translate(STRING.DETAILS_LABEL_CAMERA)}
        </span>
        <span className={styles.fieldValue}>WIP</span>
      </p>
    </div>
  </>
)
