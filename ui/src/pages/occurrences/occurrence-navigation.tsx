import { Occurrence } from 'data-services/models/occurrence'
import { ChevronLeftIcon, ChevronRightIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
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

  return {
    prevId,
    nextId,
    onPrev: () => {
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
    },
    onNext: () => {
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
    },
  }
}

export const OccurrenceNavigation = ({
  occurrences,
}: {
  occurrences?: Occurrence[]
}) => {
  const { prevId, nextId, onPrev, onNext } =
    useOccurrenceNavigation(occurrences)

  return (
    <>
      <Button
        className="absolute top-[50%] -left-8 -translate-x-full -translate-y-1/2 z-50"
        disabled={!prevId}
        onClick={onPrev}
        size="icon"
        variant="outline"
      >
        <ChevronLeftIcon className="w-4 h-4" />
      </Button>
      <Button
        className="absolute top-[50%] -right-8 translate-x-full -translate-y-1/2 z-50"
        disabled={!nextId}
        onClick={onNext}
        size="icon"
        variant="outline"
      >
        <ChevronRightIcon className="w-4 h-4" />
      </Button>
    </>
  )
}
