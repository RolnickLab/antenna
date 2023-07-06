import { ReactNode, RefObject, useEffect, useRef } from 'react'
import styles from './capture-list.module.scss'

export const CaptureList = ({
  children,
  hasMore,
  isLoading,
  innerRef,
  onNext,
}: {
  children: ReactNode
  hasMore?: boolean
  innerRef?: RefObject<HTMLDivElement>
  isLoading?: boolean
  onNext: () => void
}) => {
  const nextLoader = useRef(null)

  useEffect(() => {
    if (!hasMore || isLoading) {
      return
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          onNext()
        }
      },
      { threshold: 1 }
    )

    if (nextLoader.current) {
      observer.observe(nextLoader.current)
    }

    return () => {
      if (nextLoader.current) {
        observer.unobserve(nextLoader.current)
      }
    }
  }, [nextLoader, onNext, hasMore, isLoading])

  return (
    <div ref={innerRef} className={styles.captures}>
      {children}
      <p className={styles.message}>
        {isLoading ? 'Loading...' : hasMore ? '' : 'No more items to show'}
      </p>
      <div ref={nextLoader} />
    </div>
  )
}
