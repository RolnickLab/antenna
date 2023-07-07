import classNames from 'classnames'
import { Capture } from 'data-services/models/capture'
import { CaptureList } from 'design-system/components/capture-list/capture-list'
import { CaptureRow } from 'design-system/components/capture-list/capture-row/capture-row'
import {
  IconButton,
  IconButtonShape,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { RefObject, createRef, useEffect, useMemo, useRef } from 'react'
import { STRING, translate } from 'utils/language'
import styles from './capture-picker.module.scss'

export const CapturePicker = ({
  activeCaptureId,
  captures,
  detectionsMaxCount,
  hasMore,
  isLoading,
  onNext,
  setActiveCaptureId,
}: {
  activeCaptureId?: string
  captures: Capture[]
  detectionsMaxCount: number
  hasMore?: boolean
  isLoading?: boolean
  onNext: () => void
  setActiveCaptureId: (captureId: string) => void
}) => {
  const activeCaptureIndex = captures.findIndex(
    (capture) => capture.id === activeCaptureId
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
    if (!activeCaptureId) {
      return
    }
    captureRefs[activeCaptureId]?.current?.scrollIntoView({
      behavior: 'smooth',
      block: 'nearest',
      inline: 'nearest',
    })
  }, [activeCaptureId])

  return (
    <>
      <CaptureList
        innerRef={scrollContainerRef}
        hasMore={hasMore}
        isLoading={isLoading}
        onNext={onNext}
      >
        {captures.map((capture) => {
          const isActive = activeCaptureId === capture.id

          return (
            <CaptureRow
              key={capture.id}
              capture={{
                details: `${capture.numDetections} ${translate(
                  STRING.DETAILS_LABEL_DETECTIONS
                )}`,
                scale: capture.numDetections / detectionsMaxCount,
                timeLabel: capture.timeLabel,
              }}
              innerRef={captureRefs[capture.id]}
              isActive={isActive}
              isEmpty={capture.numDetections === 0}
              onClick={() => setActiveCaptureId(capture.id)}
            />
          )
        })}
      </CaptureList>
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
