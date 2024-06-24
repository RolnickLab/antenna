import { ReactNode } from 'react'
import styles from './page-header.module.scss'

interface PageHeaderProps {
  title: string
  subTitle: string
  isLoading?: boolean
  children?: ReactNode
}

export const PageHeader = ({ title, subTitle, children }: PageHeaderProps) => (
  <div className={styles.wrapper}>
    <div>
      <h1 className={styles.title}>{title}</h1>
      <h2 className={styles.subTitle}>{subTitle}</h2>
    </div>
    <div className={styles.controls}>{children}</div>
  </div>
)
