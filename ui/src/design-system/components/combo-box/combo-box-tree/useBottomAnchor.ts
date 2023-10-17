import { RefObject, useEffect, useState } from 'react'

const BOTTOM_MARGIN = 8
const UPDATE_INTERVAL = 20 // 0.02 s

const getBottomAnchor = ({
  containerRef,
  elementRef,
}: {
  containerRef: RefObject<HTMLElement>
  elementRef: RefObject<HTMLElement>
}): { top?: number; left?: number } => {
  if (!containerRef.current || !elementRef.current) {
    return {}
  }

  const containerRect = containerRef.current.getBoundingClientRect()
  const elementRect = elementRef.current.getBoundingClientRect()

  return {
    top: Math.max(
      elementRect.top + elementRect.height + BOTTOM_MARGIN,
      containerRect.top
    ),
    left: Math.max(elementRect.left, containerRect.left),
  }
}

/* Returns element bottom left anchor, within a given container */
export const useBottomAnchor = ({
  containerRef,
  elementRef,
  active,
}: {
  containerRef: RefObject<HTMLDivElement>
  elementRef: RefObject<HTMLInputElement>
  active?: boolean // When not true, updates are paused
}): { top?: number; left?: number } => {
  const [anchor, setAnchor] = useState(
    getBottomAnchor({ containerRef, elementRef })
  )

  useEffect(() => {
    setAnchor(getBottomAnchor({ containerRef, elementRef }))

    const interval = active
      ? setInterval(
          () => setAnchor(getBottomAnchor({ containerRef, elementRef })),
          UPDATE_INTERVAL
        )
      : undefined

    return () => clearInterval(interval)
  }, [active])

  return anchor
}
