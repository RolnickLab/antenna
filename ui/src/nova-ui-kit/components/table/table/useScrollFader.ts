import { DependencyList, RefObject, useEffect, useState } from 'react'

const THRESHOLD = 10

export const useScrollFader = (
  ref: RefObject<HTMLElement>,
  deps: DependencyList
) => {
  const [showScrollFader, setShowScrollFader] = useState(false)

  useEffect(() => {
    const updateState = () => {
      const element = ref.current

      if (element) {
        const hasScrollBar =
          Math.abs(element.scrollWidth - element.clientWidth) > THRESHOLD

        const distanceToEnd = Math.abs(
          element.clientWidth - (element.scrollWidth - element.scrollLeft)
        )

        setShowScrollFader(hasScrollBar && distanceToEnd > THRESHOLD)
      }
    }

    updateState()

    window.addEventListener('resize', updateState)
    ref.current?.addEventListener('scroll', updateState)

    return () => {
      window.removeEventListener('resize', updateState)
      ref.current?.removeEventListener('scroll', updateState)
    }
  }, [ref, ...deps])

  return showScrollFader
}
