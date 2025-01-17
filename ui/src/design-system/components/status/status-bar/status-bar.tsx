import styles from './status-bar.module.scss'

export const StatusBar = ({
  color,
  description,
  progress,
}: {
  color: string
  description?: string
  progress: number // Value in range [0,1]
}) => {
  if (progress < 0 || progress > 1) {
    throw Error(
      `Property progress has value ${progress}, but must in range [0,1].`
    )
  }

  return (
    <div>
      <div className={styles.barBackground}>
        <div
          className={styles.bar}
          style={{ width: `${(progress / 1) * 100}%`, backgroundColor: color }}
        />
      </div>
      {description?.length ? (
        <p className={styles.description}>{description}</p>
      ) : null}
    </div>
  )
}
