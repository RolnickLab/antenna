import { ReactNode, RefObject } from 'react'
import styles from './capture-list.module.scss'

export const CaptureList = ({
  children,
  hasMore,
  innerRef,
  numItems,
  onNext,
}: {
  children: ReactNode
  hasMore: boolean
  innerRef?: RefObject<HTMLDivElement>
  numItems: number
  onNext: () => void
}) => {
  return (
    <div id="capture-list" className={styles.captures}>
      {children}
    </div>
  )
}
