import { ReactNode } from 'react'
import styles from './page-footer.module.scss'

interface PageFooterProps {
  children?: ReactNode
}

export const PageFooter = ({ children }: PageFooterProps) => {
  if (!children) {
    return null
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.content}>{children}</div>
    </div>
  )
}
