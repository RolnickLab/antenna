import { Tooltip } from 'design-system/components/tooltip/tooltip'
import styles from './beta-info.module.scss'

const COPY = {
  LABEL: 'Beta',
  INFO: 'More info about beta status goes here?',
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
