import { Tooltip } from 'design-system/components/tooltip/tooltip'
import styles from './beta-info.module.scss'

const COPY = {
  LABEL: 'Beta',
  INFO: 'All data is considered test data and may be changed or deleted at any time. Use with caution.',
  VERSION: `Build ${__COMMIT_HASH__}`,
}

export const BetaInfo = () => {
  return (
    <div className={styles.wrapper}>
      <Tooltip content={COPY.INFO}>
        <div className={styles.badge}>{COPY.LABEL}</div>
      </Tooltip>
      <span className={styles.version}>{COPY.VERSION}</span>
    </div>
  )
}
