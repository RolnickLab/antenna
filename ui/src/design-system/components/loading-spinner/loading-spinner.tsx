import styles from './loading-spinner.module.scss'

export const LoadingSpinner = () => {
  return (
    <div className={styles.loadingSpinner}>
      <span>🦋</span>
    </div>
  )
}
