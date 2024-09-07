import { ReactNode } from 'react'
import styles from './page-footer.module.scss'

interface PageFooterProps {
  hide?: boolean
  children?: ReactNode
}

export const PageFooter = ({ hide, children }: PageFooterProps) => {
  if (!children || hide) {
    return null
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.content}>{children}</div>
    </div>
  )
}
