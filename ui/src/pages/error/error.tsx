import styles from './error.module.scss'

interface ErrorProps {
  message?: string
  details?: string
}

export const Error = ({
  message = 'Something went wrong!',
  details = 'Unknown error',
}: ErrorProps) => {
  return (
    <div className={styles.wrapper}>
      <h1 className={styles.message}>{message} 🪲</h1>
      <span className={styles.details}>{details}</span>
    </div>
  )
}
