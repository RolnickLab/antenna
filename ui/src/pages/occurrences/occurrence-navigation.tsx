import { Occurrence } from 'data-services/models/occurrence'
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { useCallback, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'

const useOccurrenceNavigation = (occurrences?: Occurrence[]) => {
  const { projectId, id } = useParams()
  const navigate = useNavigate()
  const currentIndex = occurrences?.findIndex((o) => o.id === id)
  const prevId =
    currentIndex !== undefined ? occurrences?.[currentIndex - 1]?.id : undefined
  const nextId =
    currentIndex !== undefined ? occurrences?.[currentIndex + 1]?.id : undefined

  const goToPrev = useCallback(() => {
    if (!prevId) {
      return
    }

    navigate(
      getAppRoute({
        to: APP_ROUTES.OCCURRENCE_DETAILS({
          projectId: projectId as string,
          occurrenceId: prevId,
        }),
        keepSearchParams: true,
      })
    )
  }, [nextId])

  const goToNext = useCallback(() => {
    if (!nextId) {
      return
    }

    navigate(
      getAppRoute({
        to: APP_ROUTES.OCCURRENCE_DETAILS({
          projectId: projectId as string,
          occurrenceId: nextId,
        }),
        keepSearchParams: true,
      })
    )
  }, [nextId])

  return {
    prevId,
    nextId,
    goToPrev,
    goToNext,
  }
}

export const OccurrenceNavigation = ({
  occurrences,
}: {
  occurrences?: Occurrence[]
}) => {
  const { prevId, nextId, goToPrev, goToNext } =
    useOccurrenceNavigation(occurrences)

  // Listen to key down events
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
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
        className="absolute top-[50%] -left-8 -translate-x-full -translate-y-1/2 z-50"
        disabled={!prevId}
        onClick={goToPrev}
        size="icon"
        variant="outline"
      >
        <ChevronLeftIcon className="w-4 h-4" />
      </Button>
      <Button
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
