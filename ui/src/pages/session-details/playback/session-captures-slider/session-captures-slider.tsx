import { Capture } from 'data-services/models/capture'
import { SessionDetails } from 'data-services/models/session-details'
import { TimelineTick } from 'data-services/models/timeline-tick'
import { TimestampSlider } from 'design-system/components/slider/timestamp-slider'
import { useEffect, useState } from 'react'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { dateToValue, findClosestCaptureId, valueToDate } from './utils'

export const SessionCapturesSlider = ({
  snapToDetections,
  session,
  timeline,
  activeCapture,
  setActiveCaptureId,
}: {
  snapToDetections?: boolean
  session: SessionDetails
  timeline: TimelineTick[]
  activeCapture?: Capture
  setActiveCaptureId: (captireId: string) => void
}) => {
  const [value, setValue] = useState(0)
  const startDate = session.startDate
  const endDate = session.endDate

  useEffect(() => {
    if (activeCapture) {
      setValue(dateToValue({ date: activeCapture.date, startDate, endDate }))
    }
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
    </div>
  )
}
