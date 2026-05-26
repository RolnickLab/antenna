import { ImageCarousel, ImageCellTheme } from 'design-system'
import styles from './image-table-cell.module.scss'

interface ImageTableCellProps {
  autoPlay?: boolean
  images: {
    src: string
    alt?: string
  }[]
  total?: number
  theme?: ImageCellTheme
  to?: string
}

export const ImageTableCell = (props: ImageTableCellProps) => (
  <div className={styles.container}>
    <ImageCarousel {...props} />
  </div>
)
