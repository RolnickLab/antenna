import classNames from 'classnames'
import { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Badge } from '../badge/badge'
import { Icon, IconTheme, IconType } from '../icon/icon'
import styles from './card.module.scss'

export enum CardSize {
  Medium = 'medium',
  Large = 'large',
}

interface CardProps {
  children?: ReactNode
  id?: string
  image?: {
    src: string
    alt?: string
  }
  label?: string
  maxWidth?: string
  size?: CardSize
  subTitle?: string
  title: string
  to?: string
}

export const Card = ({
  children,
  id,
  image,
  label,
  maxWidth,
  size = CardSize.Medium,
  subTitle = '',
  title,
  to,
}: CardProps) => {
  return (
    <div id={id} className={styles.container} style={{ maxWidth }}>
      <div className={styles.square}>
        {image ? (
          to ? (
            <Link to={to}>
              <img src={image.src} alt={image.alt} className={styles.image} />
            </Link>
          ) : (
            <img src={image.src} alt={image.alt} className={styles.image} />
          )
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
      <div className={styles.content}>
        <span
          className={classNames(styles.title, {
            [styles.medium]: size === CardSize.Medium,
            [styles.large]: size === CardSize.Large,
          })}
        >
          {title}
        </span>
        {subTitle ? (
          <span
            className={classNames(styles.subTitle, {
              [styles.medium]: size === CardSize.Medium,
              [styles.large]: size === CardSize.Large,
            })}
          >
            {subTitle}
          </span>
        ) : null}
        {label ? (
          <div className="absolute top-2 right-2">
            <Badge label={label} />
          </div>
        ) : null}
      </div>
      {children && <div className={styles.content}>{children}</div>}
    </div>
  )
}
