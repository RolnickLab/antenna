import classNames from 'classnames'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './card.module.scss'

export enum CardSize {
  Medium = 'medium',
  Large = 'large',
}

interface CardProps {
  title: string
  subTitle: string
  image?: {
    src: string
    alt?: string
  }
  maxWidth?: string
  size?: CardSize
}

export const Card = ({
  title,
  subTitle,
  image,
  maxWidth,
  size = CardSize.Medium,
}: CardProps) => {
  return (
    <div className={styles.container} style={{ maxWidth }}>
      <div className={styles.square}>
        {image ? (
          <img src={image.src + '?width=300&height=300'} alt={image.alt} className={styles.image} />
        ) : (
          <div className={styles.image}>
            <Icon
              type={IconType.Photograph}
              theme={IconTheme.Neutral}
              size={32}
            />
          </div>
        )}
      </div>
      <div className={styles.footer}>
        <span
          className={classNames(styles.title, {
            [styles.medium]: size === CardSize.Medium,
            [styles.large]: size === CardSize.Large,
          })}
        >
          {title}
        </span>
        <span
          className={classNames(styles.subTitle, {
            [styles.medium]: size === CardSize.Medium,
            [styles.large]: size === CardSize.Large,
          })}
        >
          {subTitle}
        </span>
      </div>
    </div>
  )
}
