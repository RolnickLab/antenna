import classNames from 'classnames'
import { EmptyState } from 'components/empty-state/empty-state'
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
  to: string
}

export const Gallery = ({
  cardSize,
  isLoading,
  items,
  renderItem,
  style,
}: {
  cardSize?: CardSize
  isLoading: boolean
  items: GalleryItem[]
  renderItem?: (item: GalleryItem) => JSX.Element
  style?: CSSProperties
}) => (
  <div
    className={classNames(styles.gallery, {
      [styles.loading]: isLoading,
      [styles.large]: cardSize === CardSize.Large,
    })}
    style={style}
  >
    {items?.map(
      (item) =>
        renderItem?.(item) ?? (
          <Link key={item.id} to={item.to}>
            <Card
              title={item.title}
              subTitle={item.subTitle}
              image={item.image}
              size={cardSize}
            />
          </Link>
        )
    )}
    {isLoading && (
      <div className={styles.loadingWrapper}>
        <LoadingSpinner />
      </div>
    )}
    {!isLoading && items.length === 0 && <EmptyState />}
  </div>
)
