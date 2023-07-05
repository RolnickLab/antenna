import classNames from 'classnames'
import { Card } from 'design-system/components/card/card'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Link } from 'react-router-dom'
import styles from './gallery.module.scss'

export const Gallery = ({
  items,
  isLoading,
}: {
  items: {
    id: string
    image: {
      src: string
      alt?: string
    }
    subTitle?: string
    title: string
    to: string
  }[]
  isLoading: boolean
}) => (
  <div className={classNames(styles.gallery, { [styles.loading]: isLoading })}>
    {items?.map((item) => (
      <Link key={item.id} to={item.to}>
        <Card
          title={item.title}
          subTitle={item.subTitle ?? ''}
          image={item.image}
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
