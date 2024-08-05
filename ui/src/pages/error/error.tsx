import styles from './error.module.scss'

interface ErrorProps {
  message?: string
  error?: any
}

export const Error = ({
  message = 'Something went wrong!',
  error,
}: ErrorProps) => {
  const details =
    error?.response?.data?.detail ?? error?.message ?? 'Unknown error'

  return (
    <div className={styles.wrapper}>
      <h1 className={styles.message}>{message} 🪲</h1>
      <span className={styles.details}>{details}</span>
    </div>
  )
}
