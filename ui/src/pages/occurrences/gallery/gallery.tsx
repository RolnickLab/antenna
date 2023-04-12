import classNames from 'classnames'
import { Occurrence } from 'data-services/models/occurrence'
import { Card } from 'design-system/components/card/card'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import styles from './gallery.module.scss'

export const Gallery = ({
  occurrences,
  isLoading,
}: {
  occurrences: Occurrence[]
  isLoading: boolean
}) => {
  return (
    <div
      className={classNames(styles.gallery, { [styles.loading]: isLoading })}
    >
      {occurrences.map((occurrence) => (
        <div className={styles.cardWrapper}>
          <Card
            key={occurrence.id}
            title={occurrence.categoryLabel}
            subTitle="WIP"
            image={occurrence.images[0]}
            maxWidth="262px"
          />
        </div>
      ))}
      {isLoading && (
        <div className={styles.loadingWrapper}>
          <LoadingSpinner />
        </div>
      )}
    </div>
  )
}
