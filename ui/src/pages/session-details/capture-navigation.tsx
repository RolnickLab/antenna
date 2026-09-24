import { CaptureDetails } from 'data-services/models/capture-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import {
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronsLeftIcon,
  ChevronsRightIcon,
} from 'lucide-react'
import { BasicTooltip, Button } from 'nova-ui-kit'
import { ReactNode, useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import {
  getNextCaptureWithDetectionsId,
  getPrevCaptureWithDetectionsId,
} from './utils'

const NavigationButton = ({
  children,
  disabled,
  label,
  onClick,
}: {
  children: ReactNode
  disabled: boolean
  label: string
  onClick: () => void
}) => (
  <BasicTooltip asChild content={label}>
    <Button
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      size="icon"
      variant="outline"
    >
      {children}
    </Button>
  </BasicTooltip>
)

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
      getPrevCaptureWithDetectionsId({ capture: activeCapture, timeline }) ??
      activeCapture.prevCaptureId

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
      getNextCaptureWithDetectionsId({ capture: activeCapture, timeline }) ??
      activeCapture.nextCaptureId

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
      <NavigationButton
        disabled={!activeCapture?.prevCaptureId}
        label={translate(STRING.PREVIOUS_CAPTURE_WITH_DETECTIONS)}
        onClick={goToPrevWithDetections}
      >
        <ChevronsLeftIcon className="w-4 h-4" />
      </NavigationButton>
      <NavigationButton
        disabled={!activeCapture?.prevCaptureId}
        label={translate(STRING.PREVIOUS_CAPTURE)}
        onClick={goToPrev}
      >
        <ChevronLeftIcon className="w-4 h-4" />
      </NavigationButton>
      <span className="pt-0.5 px-3">
        {currentIndex?.toLocaleString()} / {totalCaptures?.toLocaleString()}
      </span>
      <NavigationButton
        disabled={!activeCapture?.nextCaptureId}
        label={translate(STRING.NEXT_CAPTURE)}
        onClick={goToNext}
      >
        <ChevronRightIcon className="w-4 h-4" />
      </NavigationButton>
      <NavigationButton
        disabled={!activeCapture?.nextCaptureId}
        label={translate(STRING.NEXT_CAPTURE_WITH_DETECTIONS)}
        onClick={goToNextWithDetections}
      >
        <ChevronsRightIcon className="w-4 h-4" />
      </NavigationButton>
    </div>
  )
}
