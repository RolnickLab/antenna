import { ImageCarousel } from 'design-system/components/image-carousel/image-carousel'
import { ImageCellTheme } from '../types'
import styles from './image-table-cell.module.scss'

interface ImageTableCellProps {
  images: {
    src: string
    alt?: string
  }[]
  theme?: ImageCellTheme
  autoPlay?: boolean
}

export const ImageTableCell = (props: ImageTableCellProps) => (
  <div className={styles.container}>
    <ImageCarousel {...props} />
  </div>
)
