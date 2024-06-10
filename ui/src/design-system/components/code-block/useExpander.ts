import { DependencyList, RefObject, useEffect, useState } from 'react'

const THRESHOLD = 10

export const useExpander = (
  ref: RefObject<HTMLElement>,
  deps: DependencyList
) => {
  const [showExpander, setShowExpander] = useState(false)

  useEffect(() => {
    const updateState = () => {
      const element = ref.current

      if (element) {
        const hasScrollBar =
          Math.abs(element.scrollHeight - element.clientHeight) > THRESHOLD

        setShowExpander(hasScrollBar)
      }
    }

    updateState()

    window.addEventListener('resize', updateState)

    return () => {
      window.removeEventListener('resize', updateState)
    }
  }, [ref, ...deps])

  return showExpander
}
