import * as _Slider from '@radix-ui/react-slider'
import { Capture } from 'data-services/models/capture'
import { SessionDetails } from 'data-services/models/session-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import { TriangleIcon } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
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

  useEffect(() => {
    if (activeCapture) {
      setValue(dateToValue({ date: activeCapture.date, startDate, endDate }))
    }
  }, [activeCapture])

  return (
    <Slider
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

const Slider = ({
  labels,
  value,
  valueLabel,
  onValueChange,
  onValueCommit,
}: {
  labels: string[]
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
      step={0.01}
      value={[value]}
      onValueChange={(values) => onValueChange(values[0])}
      onValueCommit={(values) => onValueCommit(values[0])}
    >
      <_Slider.Track className={styles.sliderTrack}>
        <_Slider.Range className={styles.sliderRange} />
      </_Slider.Track>
      <_Slider.Thumb className={styles.sliderThumb}>
        {valueLabel && <span className={styles.label}>{valueLabel}</span>}
        <TriangleIcon className="text-primary" />
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
