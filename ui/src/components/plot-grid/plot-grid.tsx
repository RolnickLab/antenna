import { ReactNode } from 'react'
import styles from './plot-grid.module.scss'

export const PlotGrid = ({ children }: { children: ReactNode }) => (
  <div className={styles.container}>
    <div className={styles.grid}>{children}</div>
  </div>
)
