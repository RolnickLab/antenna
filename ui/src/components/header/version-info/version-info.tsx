import { Badge } from 'design-system/components/badge/badge'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import styles from './version-info.module.scss'

const COPY = {
  LABEL: import.meta.env.VITE_ENV_LABEL ?? 'Beta',
  INFO:
    import.meta.env.VITE_ENV_DESCRIPTION ??
    'All data is considered test data and may be changed or deleted at any time. Use with caution.',
  VERSION: import.meta.env.VITE_BUILD_VERSION ?? `Build ${__COMMIT_HASH__}`,
}

export const VersionInfo = () => (
  <div className={styles.wrapper}>
    <BasicTooltip content={COPY.INFO}>
      <Badge
        deprecated={(COPY.LABEL as string).toLowerCase().includes('deprecated')}
        label={COPY.LABEL}
      />
    </BasicTooltip>
    <span className={styles.version}>{COPY.VERSION}</span>
  </div>
)
