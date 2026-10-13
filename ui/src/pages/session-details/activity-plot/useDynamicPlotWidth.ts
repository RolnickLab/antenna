import { RefObject, useEffect, useState } from 'react'

export const useDynamicPlotWidth = (containerRef: RefObject<HTMLElement>) => {
  const [width, setWidth] = useState<number>()

  useEffect(() => {
    const updateState = () => {
      const container = containerRef.current

      if (container) {
        setWidth(container.clientWidth)
      }
    }

    updateState()

    window.addEventListener('resize', updateState)

    return () => {
      window.removeEventListener('resize', updateState)
    }
  }, [containerRef])

  return width
}
