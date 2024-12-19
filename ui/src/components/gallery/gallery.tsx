import classNames from 'classnames'
import { EmptyState } from 'components/empty-state/empty-state'
import { ErrorState } from 'components/error-state/error-state'
import { Card, CardSize } from 'design-system/components/card/card'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import styles from './gallery.module.scss'

interface GalleryItem {
  id: string
  image?: {
    src: string
    alt?: string
  }
  subTitle?: string
  title: string
  to: string | undefined
}

export const Gallery = ({
  cardSize,
  error,
  isLoading,
  items,
  renderItem,
  style,
}: {
  cardSize?: CardSize
  error?: any
  isLoading: boolean
  items: GalleryItem[]
  renderItem?: (item: GalleryItem) => JSX.Element
  style?: CSSProperties
}) => {
  if (isLoading) {
    return (
      <div className={styles.loadingWrapper}>
        <LoadingSpinner />
      </div>
    )
  }

  if (error) {
    return <ErrorState error={error} />
  }

  if (items.length === 0) {
    return <EmptyState />
  }

  return (
    <div
      className={classNames(styles.gallery, {
        [styles.large]: cardSize === CardSize.Large,
      })}
      style={style}
    >
      {items?.map(
        (item) =>
          renderItem?.(item) ??
          (item.to ? (
            <Link key={item.id} to={item.to}>
              <Card
                title={item.title}
                subTitle={item.subTitle}
                image={item.image}
                size={cardSize}
              />
            </Link>
          ) : (
            <Card
              key={item.id}
              title={item.title}
              subTitle={item.subTitle}
              image={item.image}
              size={cardSize}
            />
          ))
      )}

      {!isLoading && items.length === 0 && <EmptyState />}
    </div>
  )
}
