import classNames from 'classnames'
import { Occurrence } from 'data-services/models/occurrence'
import { Card } from 'design-system/components/card/card'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Link } from 'react-router-dom'
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
        <Link to={`/occurrences/${occurrence.id}`}>
          <Card
            key={occurrence.id}
            title={occurrence.categoryLabel}
            subTitle="WIP"
            image={occurrence.images[0]}
          />
        </Link>
      ))}
      {isLoading && (
        <div className={styles.loadingWrapper}>
          <LoadingSpinner />
        </div>
      )}
    </div>
  )
}
