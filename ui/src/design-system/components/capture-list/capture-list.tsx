import { ReactNode, RefObject } from 'react'
import styles from './capture-list.module.scss'

export const CaptureList = ({
  innerRef,
  children,
}: {
  innerRef?: RefObject<HTMLDivElement>
  children: ReactNode
}) => {
  return (
    <div className={styles.captures} ref={innerRef}>
      {children}
    </div>
  )
}
