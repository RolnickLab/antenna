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
  }, [nextLoader, onNext])

  return (
    <div ref={innerRef} className={styles.captures}>
      {children}
      <p className={styles.message}>
        {!hasMore ? 'No more items to show' : isLoading ? 'Loading...' : ''}
      </p>
      <div ref={nextLoader} />
    </div>
  )
}
