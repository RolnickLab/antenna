import { CaptureDetails } from 'data-services/models/capture-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
} from 'lucide-react'
import { BasicTooltip, Button } from 'nova-ui-kit'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { findClosestCaptureId } from './utils'

export const CaptureNavigation = ({
  activeCapture,
  timeline,
  setActiveCaptureId,
}: {
  activeCapture?: CaptureDetails
  timeline: TimelineTick[]
  setActiveCaptureId: (captureId: string) => void
}) => {
  const [currentIndex, setCurrentIndex] = useState(activeCapture?.currentIndex)
  const [totalCaptures, setTotalCaptures] = useState(
    activeCapture?.totalCaptures
  )

  useEffect(() => {
    if (activeCapture) {
      setCurrentIndex(activeCapture.currentIndex)
      setTotalCaptures(activeCapture.totalCaptures)
    }
  }, [activeCapture])

  const goToPrev = () => {
    if (!activeCapture?.prevCaptureId) {
      return
    }

    setActiveCaptureId(activeCapture.prevCaptureId)
  }

  const goToPrevWithDetections = () => {
    if (!activeCapture) {
      return
    }

    const prevCaptureId =
      findClosestCaptureId({
        maxDate: activeCapture.date,
        snapToDetections: true,
        targetDate: activeCapture.date,
        timeline,
      }) ?? activeCapture.prevCaptureId

    if (prevCaptureId) {
      setActiveCaptureId(prevCaptureId)
    }
  }

  const goToNext = () => {
    if (!activeCapture?.nextCaptureId) {
      return
    }

    setActiveCaptureId(activeCapture.nextCaptureId)
  }

  const goToNextWithDetections = () => {
    if (!activeCapture) {
      return
    }

    const nextCaptureId =
      findClosestCaptureId({
        minDate: activeCapture.date,
        snapToDetections: true,
        targetDate: activeCapture.date,
        timeline,
      }) ?? activeCapture.nextCaptureId

    if (nextCaptureId) {
      setActiveCaptureId(nextCaptureId)
    }
  }

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
    <div className="flex items-center justify-center gap-1">
      <BasicTooltip asChild content={translate(STRING.SNAP_TO_DETECTIONS)}>
        <Button
          aria-label={translate(STRING.SNAP_TO_DETECTIONS)}
          disabled={!activeCapture?.prevCaptureId}
          onClick={goToPrevWithDetections}
          size="icon"
          variant="outline"
        >
          <ChevronsLeftIcon className="w-4 h-4" />
        </Button>
      </BasicTooltip>
      <Button
        aria-label={translate(STRING.PREVIOUS)}
        disabled={!activeCapture?.prevCaptureId}
        onClick={goToPrev}
        size="icon"
        variant="outline"
      >
        <ChevronLeftIcon className="w-4 h-4" />
      </Button>
      <span className="pt-0.5 px-3">
        {currentIndex?.toLocaleString()} / {totalCaptures?.toLocaleString()}
      </span>
      <Button
        aria-label={translate(STRING.NEXT)}
        disabled={!activeCapture?.nextCaptureId}
        onClick={goToNext}
        size="icon"
        variant="outline"
      >
        <ChevronRightIcon className="w-4 h-4" />
      </Button>
      <BasicTooltip asChild content={translate(STRING.SNAP_TO_DETECTIONS)}>
        <Button
          aria-label={translate(STRING.SNAP_TO_DETECTIONS)}
          disabled={!activeCapture?.nextCaptureId}
          onClick={goToNextWithDetections}
          size="icon"
          variant="outline"
        >
          <ChevronsRightIcon className="w-4 h-4" />
        </Button>
      </BasicTooltip>
    </div>
  )
}
