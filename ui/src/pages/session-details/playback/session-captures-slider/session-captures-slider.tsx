import { Capture } from 'data-services/models/capture'
import { TimestampSlider } from 'design-system/components/slider/timestamp-slider'
import { useEffect, useState } from 'react'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { dateToValue, findClosestCapture, valueToDate } from './utils'

export const SessionCapturesSlider = ({
  captures,
  activeCapture,
  setActiveCapture,
}: {
  captures: Capture[]
  activeCapture?: Capture
  setActiveCapture: (capture: Capture) => void
}) => {
  const [value, setValue] = useState(0)
  const startDate = captures[0].date
  const endDate = captures[captures.length - 1].date

  useEffect(() => {
    setValue(
      activeCapture
        ? dateToValue({ date: activeCapture.date, startDate, endDate })
        : 0
    )
  }, [activeCapture])

  return (
    <div>
      <TimestampSlider
        labels={[
          getFormatedTimeString({ date: startDate }),
          getFormatedTimeString({ date: endDate }),
        ]}
        value={value}
        valueLabel={getFormatedTimeString({
          date: valueToDate({ value, startDate, endDate }),
          options: { second: true },
        })}
        onValueChange={(value) => {
          setValue(value)
        }}
        onValueCommit={(value) => {
          // Update active capture based on date
          const targetDate = valueToDate({ value, startDate, endDate })
          const capture = findClosestCapture(captures, targetDate)
          if (capture) {
            setActiveCapture(capture)
          }
        }}
      />
    </div>
  )
}
