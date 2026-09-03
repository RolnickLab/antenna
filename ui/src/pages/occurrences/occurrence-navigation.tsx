import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useCallback, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'

// Ordered items the modal can page through. Only the id is needed: on the occurrences
// list these are Occurrence models; on the taxa list they are the per-row example
// occurrences, so paging steps to the next taxon's example.
type NavItem = { id: string }

const useOccurrenceNavigation = (
  items?: NavItem[],
  currentId?: string,
  onNavigate?: (id: string) => void
) => {
  const { projectId, id: routeId } = useParams()
  const navigate = useNavigate()
  const activeId = currentId ?? routeId
  const currentIndex = items?.findIndex((o) => o.id === activeId)
  const hasCurrent = currentIndex !== undefined && currentIndex >= 0
  const prevId = hasCurrent ? items?.[currentIndex - 1]?.id : undefined
  const nextId = hasCurrent ? items?.[currentIndex + 1]?.id : undefined

  const goTo = useCallback(
    (targetId?: string) => {
      if (!targetId) {
        return
      }
      // The taxa list keeps the modal open and swaps the ?verifyOccurrence id in place;
      // the occurrences list routes to that occurrence's detail page.
      if (onNavigate) {
        onNavigate(targetId)
        return
      }
      navigate(
        getAppRoute({
          to: APP_ROUTES.OCCURRENCE_DETAILS({
            projectId: projectId as string,
            occurrenceId: targetId,
          }),
          keepSearchParams: true,
        })
      )
    },
    [navigate, onNavigate, projectId]
  )

  const goToPrev = useCallback(() => goTo(prevId), [goTo, prevId])
  const goToNext = useCallback(() => goTo(nextId), [goTo, nextId])

  return {
    prevId,
    nextId,
    goToPrev,
    goToNext,
  }
}

export const OccurrenceNavigation = ({
  occurrences,
  currentId,
  onNavigate,
}: {
  occurrences?: NavItem[]
  currentId?: string
  onNavigate?: (id: string) => void
}) => {
  const { prevId, nextId, goToPrev, goToNext } = useOccurrenceNavigation(
    occurrences,
    currentId,
    onNavigate
  )

  // Listen to key down events
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (
        document.activeElement?.matches('input') ||
        document.activeElement?.role === 'tab'
      ) {
        return
      }

      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        goToPrev()
      } else if (e.key === 'ArrowRight') {
        e.preventDefault()
        goToNext()
      }
    }

    document.addEventListener('keydown', onKeyDown)

    return () => document.removeEventListener('keydown', onKeyDown)
  }, [goToPrev, goToNext])

  return (
    <>
      <Button
        aria-label={translate(STRING.PREVIOUS)}
        className="absolute top-[50%] -left-8 -translate-x-full -translate-y-1/2 z-50"
        disabled={!prevId}
        onClick={goToPrev}
        size="icon"
        variant="outline"
      >
        <ChevronLeftIcon className="w-4 h-4" />
      </Button>
      <Button
        aria-label={translate(STRING.NEXT)}
        className="absolute top-[50%] -right-8 translate-x-full -translate-y-1/2 z-50"
        disabled={!nextId}
        onClick={goToNext}
        size="icon"
        variant="outline"
      >
        <ChevronRightIcon className="w-4 h-4" />
      </Button>
    </>
  )
}
