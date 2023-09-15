import classNames from 'classnames'
import { Card, CardSize } from 'design-system/components/card/card'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import styles from './gallery.module.scss'

export const Gallery = ({
  cardSize,
  isLoading,
  items,
  style,
}: {
  cardSize?: CardSize
  isLoading: boolean
  items: {
    id: string
    image?: {
      src: string
      alt?: string
    }
    subTitle?: string
    title: string
    to: string
  }[]

  style?: CSSProperties
}) => (
  <div
    className={classNames(styles.gallery, {
      [styles.loading]: isLoading,
      [styles.large]: cardSize === CardSize.Large,
    })}
    style={style}
  >
    {items?.map((item) => (
      <Link key={item.id} to={item.to}>
        <Card
          title={item.title}
          subTitle={item.subTitle ?? ''}
          image={item.image}
          size={cardSize}
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
