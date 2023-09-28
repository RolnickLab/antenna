import styles from './status-label.module.scss'

export const StatusLabel = ({ label }: { label: string }) => (
  <span className={styles.statusLabel}>{label}</span>
)
