import classNames from 'classnames'
import { ImageCellTheme } from '../types'
import styles from './image-table-cell.module.scss'

interface ImageTableCellProps {
  image: {
    src: string
    alt?: string
  }
  theme?: ImageCellTheme
}

export const ImageTableCell = ({
  image,
  theme = ImageCellTheme.Default,
}: ImageTableCellProps) => {
  return (
    <div className={styles.container}>
      <div
        className={classNames(styles.imageBox, {
          [styles.light]: theme === ImageCellTheme.Light,
        })}
      >
        <img src={image.src} alt={image.alt} className={styles.image} />
      </div>
    </div>
  )
}
