import styles from './loading-spinner.module.scss'

export const LoadingSpinner = ({ size = 56 }: { size?: number }) => {
  return (
    <div
      className={styles.loadingSpinner}
      style={{
        width: `${size}px`,
        height: `${size}px`,
        borderWidth: `${size / 8}px`,
      }}
    />
  )
}
