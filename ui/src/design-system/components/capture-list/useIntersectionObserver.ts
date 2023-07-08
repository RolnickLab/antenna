import { useEffect, useRef } from 'react'

export const useIntersectionObserver = ({
  onIntersect,
}: {
  onIntersect: () => void
}) => {
  const ref = useRef(null)

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          onIntersect()
        }
      },
      { threshold: 1 }
    )

    if (ref.current) {
      observer.observe(ref.current)
    }

    return () => {
      if (ref.current) {
        observer.unobserve(ref.current)
      }
    }
  }, [ref, onIntersect])

  return ref
}
