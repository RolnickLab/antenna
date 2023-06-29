import classNames from 'classnames'
import {
  IconButton,
  IconButtonShape,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { RefObject, createRef, useEffect, useMemo, useRef } from 'react'
import { CaptureRow } from '../capture-row/capture-row'
import captures from '../captures.json' // TODO: Update when we have real data
import styles from './capture-picker.module.scss'

export const CapturePicker = ({
  activeCaptureId,
  setActiveCaptureId,
}: {
  activeCaptureId: number
  setActiveCaptureId: (captureID: number) => void
}) => {
  const activeCaptureIndex = captures.findIndex(
    (capture) => capture.id === activeCaptureId
  )

  const maxAmountDetections = Math.max(
    ...captures.map((capture) => capture.num_detections)
  )

  const scrollContainerRef = useRef<HTMLDivElement>(null)

  const captureRefs = useMemo(
    () =>
      captures.reduce(
        (refs: { [id: string]: RefObject<HTMLDivElement> }, capture) => {
          refs[capture.id] = createRef<HTMLDivElement>()
          return refs
        },
        {}
      ),
    [captures]
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
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        goToPrev()
      } else if (e.key === 'ArrowDown') {
        e.preventDefault()
        goToNext()
      }
    }

    document.addEventListener('keydown', onKeyDown)

    return () => document.removeEventListener('keydown', onKeyDown)
  }, [goToPrev, goToNext])

  // Scroll active element into view
  useEffect(() => {
    captureRefs[activeCaptureId].current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'nearest',
    })
  }, [activeCaptureId])

  return (
    <>
      <div className={styles.captures} ref={scrollContainerRef}>
        {captures.map((capture) => {
          const isActive = activeCaptureId === capture.id

          return (
            <CaptureRow
              key={capture.id}
              capture={capture}
              innerRef={captureRefs[capture.id]}
              isActive={isActive}
              scale={capture.num_detections / maxAmountDetections}
              onClick={() => setActiveCaptureId(capture.id)}
            />
          )
        })}
      </div>
      <div
        className={classNames(styles.scrollFader, styles.alignTop)}
        style={{ width: scrollContainerRef.current?.clientWidth }}
      />
      <div
        className={classNames(styles.scrollFader, styles.alignBottom)}
        style={{ width: scrollContainerRef.current?.clientWidth }}
      />
      <div className={classNames(styles.buttonContainer, styles.alignTop)}>
        <IconButton
          icon={IconType.ToggleLeft}
          shape={IconButtonShape.RoundLarge}
          theme={IconButtonTheme.Neutral}
          disabled={activeCaptureIndex - 1 < 0}
          onClick={goToPrev}
        />
      </div>
      <div className={classNames(styles.buttonContainer, styles.alignBottom)}>
        <IconButton
          icon={IconType.ToggleRight}
          shape={IconButtonShape.RoundLarge}
          theme={IconButtonTheme.Neutral}
          disabled={activeCaptureIndex + 1 > captures.length - 1}
          onClick={goToNext}
        />
      </div>
    </>
  )
}
