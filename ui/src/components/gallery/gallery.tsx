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
  label?: string
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
    <div className={styles.gallery} style={style}>
      {items?.map(
        (item) =>
          renderItem?.(item) ??
          (item.to ? (
            <Link id={item.id} key={item.id} to={item.to}>
              <Card
                image={item.image}
                size={cardSize}
                subTitle={item.subTitle}
                title={item.title}
              />
            </Link>
          ) : (
            <Card
              id={item.id}
              image={item.image}
              key={item.id}
              size={cardSize}
              subTitle={item.subTitle}
              title={item.title}
            />
          ))
      )}
      {!isLoading && items.length === 0 && <EmptyState />}
    </div>
  )
}
