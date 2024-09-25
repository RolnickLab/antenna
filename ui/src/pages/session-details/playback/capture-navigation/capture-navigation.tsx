import { CaptureDetails } from 'data-services/models/capture-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import {
  IconButton,
  IconButtonShape,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useEffect, useState } from 'react'
import { findClosestCaptureId } from '../utils'
import styles from './capture-navigation.module.scss'

export const CaptureNavigation = ({
  activeCapture,
  snapToDetections,
  timeline,
  setActiveCaptureId,
}: {
  activeCapture?: CaptureDetails
  snapToDetections?: boolean
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
    if (!activeCapture) {
      return
    }

    const prevCaptureId = snapToDetections
      ? findClosestCaptureId({
          maxDate: activeCapture.date,
          snapToDetections: true,
          targetDate: activeCapture.date,
          timeline,
        })
      : activeCapture.prevCaptureId

    if (prevCaptureId) {
      setActiveCaptureId(prevCaptureId)
    }
  }

  const goToNext = () => {
    if (!activeCapture) {
      return
    }

    const nextCaptureId = snapToDetections
      ? findClosestCaptureId({
          minDate: activeCapture.date,
          snapToDetections: true,
          targetDate: activeCapture.date,
          timeline,
        })
      : activeCapture.nextCaptureId

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
    <div className={styles.wrapper}>
      <IconButton
        icon={IconType.ToggleLeft}
        shape={IconButtonShape.RoundLarge}
        theme={IconButtonTheme.Neutral}
        disabled={!activeCapture?.prevCaptureId}
        onClick={goToPrev}
      />
      {totalCaptures && (
        <span>
          {currentIndex?.toLocaleString()} / {totalCaptures.toLocaleString()}
        </span>
      )}
      <IconButton
        icon={IconType.ToggleRight}
        shape={IconButtonShape.RoundLarge}
        theme={IconButtonTheme.Neutral}
        disabled={!activeCapture?.nextCaptureId}
        onClick={goToNext}
      />
    </div>
  )
}
