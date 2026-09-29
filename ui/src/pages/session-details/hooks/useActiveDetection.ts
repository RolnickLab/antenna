import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

const SEARCH_PARAM_KEY = 'detection'

/**
 * The detection a link points at, which is the one handle that survives regrouping.
 *
 * A link built on an occurrence rots as soon as that detection is merged, split or
 * extended into a different occurrence. A detection's id never changes, so a link built
 * on one still opens the right box on the right capture, whatever track it now belongs to.
 */
/**
 * The page you are on, pointed at one detection.
 *
 * Built from the current URL so the capture travels with it, which is what makes the
 * link resolve without the reader having to know which capture the detection sits on.
 */
export const buildDetectionLink = (href: string, detectionId: string) => {
  const url = new URL(href)
  url.searchParams.set(SEARCH_PARAM_KEY, detectionId)

  return url.toString()
}

export const useActiveDetection = () => {
  const [searchParams, setSearchParams] = useSearchParams()

  const activeDetectionId = searchParams.get(SEARCH_PARAM_KEY) ?? undefined

  const setActiveDetectionId = useCallback(
    (detectionId?: string) => {
      if (detectionId) {
        searchParams.set(SEARCH_PARAM_KEY, detectionId)
      } else {
        searchParams.delete(SEARCH_PARAM_KEY)
      }

      setSearchParams(searchParams, { replace: true })
    },
    [searchParams, setSearchParams]
  )

  return { activeDetectionId, setActiveDetectionId }
}
