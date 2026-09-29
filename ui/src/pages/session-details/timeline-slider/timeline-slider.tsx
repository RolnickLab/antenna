import * as _Slider from '@radix-ui/react-slider'
import { Capture } from 'data-services/models/capture'
import { SessionDetails } from 'data-services/models/session-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import { TriangleIcon } from 'lucide-react'
import { KeyboardEvent, useEffect, useMemo, useState } from 'react'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { STRING, translate } from 'utils/language'
import {
  getCaptureIndex,
  getKeyStep,
  getNavigableCaptures,
  getStepTarget,
  NavigableCapture,
} from '../activity-plot/timeline-navigation'
import { dateToValue, findClosestCaptureId, valueToDate } from '../utils'
import styles from './styles.module.scss'

export const TimelineSlider = ({
  activeCapture,
  session,
  setActiveCaptureId,
  snapToDetections,
  timeline,
}: {
  activeCapture?: Capture
  session: SessionDetails
  setActiveCaptureId: (captireId: string) => void
  snapToDetections?: boolean
  timeline: TimelineTick[]
}) => {
  const [value, setValue] = useState(0)
  const startDate = session.startDate
  const endDate = session.endDate
  const showLabels = session.startDate.getTime() !== session.endDate.getTime()
  const captures = useMemo(() => getNavigableCaptures(timeline), [timeline])
  const captureIndex = getCaptureIndex({
    captureId: activeCapture?.id,
    captures,
    date: activeCapture?.date,
  })

  useEffect(() => {
    if (activeCapture) {
      setValue(dateToValue({ date: activeCapture.date, startDate, endDate }))
    }
  }, [activeCapture])

  // Radix would step the handle by a hundredth of a percent, and the page-wide arrow
  // shortcut would move a capture of its own, so a key this can answer is claimed from
  // both. A key it cannot answer is left alone, keeping that shortcut working.
  const onKeyDown = (event: KeyboardEvent<HTMLSpanElement>) => {
    const step = getKeyStep(event.key)
    const target =
      step === undefined
        ? undefined
        : getStepTarget({ captures, index: captureIndex, step })

    if (!target) {
      return
    }

    event.preventDefault()
    event.stopPropagation()

    if (target.captureId !== activeCapture?.id) {
      setActiveCaptureId(target.captureId)
    }
  }

  return (
    <Slider
      ariaLabel={translate(STRING.TIMELINE_POSITION_LABEL)}
      ariaValueText={getValueText({ activeCapture, captureIndex, captures })}
      onKeyDown={onKeyDown}
      labels={
        showLabels
          ? [
              getFormatedTimeString({ date: startDate }),
              getFormatedTimeString({ date: endDate }),
            ]
          : []
      }
      value={value}
      onValueChange={(value) => setValue(value)}
      onValueCommit={(value) => {
        // Update active capture based on date
        const targetDate = valueToDate({ value, startDate, endDate })
        const captureId = findClosestCaptureId({
          snapToDetections,
          targetDate,
          timeline,
        })

        if (captureId && activeCapture?.id !== captureId) {
          setActiveCaptureId(captureId)
        } else if (activeCapture) {
          setValue(
            dateToValue({ date: activeCapture.date, startDate, endDate })
          )
        }
      }}
    />
  )
}

// The handle reports the capture it rests on, in place of the percentage a slider
// would otherwise announce.
const getValueText = ({
  activeCapture,
  captureIndex,
  captures,
}: {
  activeCapture?: Capture
  captureIndex: number
  captures: NavigableCapture[]
}) => {
  if (!activeCapture) {
    return undefined
  }

  const time = getFormatedTimeString({ date: activeCapture.date })

  if (captureIndex === -1) {
    return time
  }

  return translate(STRING.TIMELINE_POSITION_VALUE, {
    index: captureIndex + 1,
    time,
    total: captures.length,
  })
}

const Slider = ({
  ariaLabel,
  ariaValueText,
  labels,
  onKeyDown,
  value,
  valueLabel,
  onValueChange,
  onValueCommit,
}: {
  ariaLabel: string
  ariaValueText?: string
  labels: string[]
  onKeyDown: (event: KeyboardEvent<HTMLSpanElement>) => void
  value: number
  valueLabel?: string
  onValueChange: (value: number) => void
  onValueCommit: (value: number) => void
}) => (
  <div className={styles.timestampSlider}>
    <_Slider.Root
      className={styles.sliderRoot}
      min={0}
      max={100}
      onKeyDown={onKeyDown}
      step={0.01}
      value={[value]}
      onValueChange={(values) => onValueChange(values[0])}
      onValueCommit={(values) => onValueCommit(values[0])}
    >
      <_Slider.Track className={styles.sliderTrack}>
        <_Slider.Range className={styles.sliderRange} />
      </_Slider.Track>
      <_Slider.Thumb
        aria-label={ariaLabel}
        aria-valuetext={ariaValueText}
        className={`${styles.sliderThumb} rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2`}
      >
        {valueLabel && <span className={styles.label}>{valueLabel}</span>}
        <TriangleIcon className="text-primary bg-background" />
      </_Slider.Thumb>
    </_Slider.Root>
    <div className={styles.labels}>
      {labels.map((label, index) => (
        <span key={index} className={styles.label}>
          {label}
        </span>
      ))}
    </div>
  </div>
)
