import { Capture } from 'data-services/models/capture'
import {
  IconButton,
  IconButtonShape,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { useEffect } from 'react'
import styles from './capture-navigation.module.scss'

export const CaptureNavigation = ({
  activeCaptureId,
  captures,
  setActiveCaptureId,
}: {
  activeCaptureId?: string
  captures: Capture[]
  setActiveCaptureId: (captureId: string) => void
}) => {
  const activeCaptureIndex = captures.findIndex(
    (capture) => capture.id === activeCaptureId
  )

  const goToPrev = () => {
    const prevCapture = captures[activeCaptureIndex - 1]
    if (prevCapture) {
      setActiveCaptureId(prevCapture.id)
    }
  }

  const goToNext = () => {
    const nextCapture = captures[activeCaptureIndex + 1]
    if (nextCapture) {
      setActiveCaptureId(nextCapture.id)
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

  if (!captures.length) {
    return null
  }

  return (
    <div className={styles.buttonContainer}>
      <IconButton
        icon={IconType.ToggleLeft}
        shape={IconButtonShape.RoundLarge}
        theme={IconButtonTheme.Neutral}
        disabled={activeCaptureIndex - 1 < 0}
        onClick={goToPrev}
      />
      <span>
        {activeCaptureIndex + 1} / {captures.length}
      </span>
      <IconButton
        icon={IconType.ToggleRight}
        shape={IconButtonShape.RoundLarge}
        theme={IconButtonTheme.Neutral}
        disabled={activeCaptureIndex + 1 > captures.length - 1}
        onClick={goToNext}
      />
    </div>
  )
}
