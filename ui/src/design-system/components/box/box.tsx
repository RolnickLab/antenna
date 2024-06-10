import { ReactNode } from 'react'
import styles from './box.module.scss'

export const Box = ({ children }: { children: ReactNode }) => (
  <div className={styles.box}>
    <div className={styles.boxContent}>{children}</div>
  </div>
)
