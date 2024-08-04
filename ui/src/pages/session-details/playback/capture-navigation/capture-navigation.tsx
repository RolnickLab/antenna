import { CaptureDetails } from 'data-services/models/capture-details'
import {
  IconButton,
  IconButtonShape,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useEffect } from 'react'
import styles from './capture-navigation.module.scss'

export const CaptureNavigation = ({
  activeCapture,
  setActiveCaptureId,
}: {
  activeCapture: CaptureDetails
  setActiveCaptureId: (captureId: string) => void
}) => {
  const goToPrev = () => {
    if (activeCapture.prevCaptureId) {
      setActiveCaptureId(activeCapture.prevCaptureId)
    }
  }

  const goToNext = () => {
    if (activeCapture.nextCaptureId) {
      setActiveCaptureId(activeCapture.nextCaptureId)
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
        disabled={!activeCapture.prevCaptureId}
        onClick={goToPrev}
      />
      {activeCapture && (
        <span>
          {activeCapture.currentIndex} / {activeCapture.totalCaptures}
        </span>
      )}
      <IconButton
        icon={IconType.ToggleRight}
        shape={IconButtonShape.RoundLarge}
        theme={IconButtonTheme.Neutral}
        disabled={!activeCapture.nextCaptureId}
        onClick={goToNext}
      />
    </div>
  )
}
