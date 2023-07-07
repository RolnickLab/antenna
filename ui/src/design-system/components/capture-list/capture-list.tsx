/* eslint-disable @typescript-eslint/no-empty-function */

import { ReactNode, RefObject, useCallback, useEffect } from 'react'
import styles from './capture-list.module.scss'
import { useIntersectionObserver } from './useIntersectionObserver'

export const CaptureList = ({
  children,
  hasNext,
  hasPrev,
  isLoadingNext,
  isLoadingPrev,
  innerRef,
  onNext = () => {},
  onPrev = () => {},
}: {
  children: ReactNode
  hasNext?: boolean
  hasPrev?: boolean
  innerRef?: RefObject<HTMLDivElement>
  isLoadingNext?: boolean
  isLoadingPrev?: boolean
  onNext?: () => void
  onPrev?: () => void
}) => {
  const _onNext = useCallback(() => {
    if (!isLoadingNext && hasNext) {
      onNext()
    }
  }, [isLoadingNext, hasNext])

  const _onPrev = useCallback(() => {
    if (!isLoadingPrev && hasPrev) {
      onPrev()
    }
  }, [isLoadingPrev, hasPrev])

  const nextLoader = useIntersectionObserver({ onIntersect: _onNext })
  const prevLoader = useIntersectionObserver({ onIntersect: _onPrev })

  useEffect(() => {
    const scrollContainer = innerRef?.current
    if (scrollContainer) {
      scrollContainer.scrollTop = scrollContainer.scrollHeight
    }
  }, [innerRef?.current])

  return (
    <div ref={innerRef} className={styles.captures}>
      <div ref={prevLoader} />
      <MessageRow
        message={isLoadingPrev ? 'Loading...' : hasPrev ? '' : 'Session start'}
      />
      {children}
      <MessageRow
        message={isLoadingNext ? 'Loading...' : hasNext ? '' : 'Session end'}
      />
      <div ref={nextLoader} />
    </div>
  )
}

const MessageRow = ({ message }: { message: string }) => (
  <p className={styles.message}>
    <span className={styles.messageText}>{message}</span>
  </p>
)
