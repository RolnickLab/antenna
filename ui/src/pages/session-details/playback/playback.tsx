import { useInfiniteCaptures } from 'data-services/hooks/sessions/useInfiniteCaptures'
import { Capture } from 'data-services/models/capture'
import { SessionDetails } from 'data-services/models/session-details'
import {
  Checkbox,
  CheckboxTheme,
} from 'design-system/components/checkbox/checkbox'
import { TimestampSlider } from 'design-system/components/slider/timestamp-slider'
import { useState } from 'react'
import { getFormatedTimeString } from 'utils/date/getFormatedTimeString/getFormatedTimeString'
import { useThreshold } from 'utils/threshold/thresholdContext'
import { CaptureDetails } from './capture-details/capture-details'
import { CaptureNavigation } from './capture-navigation/capture-navigation'
import { Frame } from './frame/frame'
import styles from './playback.module.scss'
import { ThresholdSlider } from './threshold-slider/threshold-slider'
import { useActiveCapture, useActiveCaptureId } from './useActiveCapture'

export const Playback = ({ session }: { session: SessionDetails }) => {
  const { threshold } = useThreshold()
  const { captures = [] } = useInfiniteCaptures(
    session.id,
    session.captureOffset,
    0
  )
  const { activeCapture, setActiveCapture } = useActiveCapture(captures)
  const [showDetections, setShowDetections] = useState(true)
  const { activeCaptureId } = useActiveCaptureId()

  if (!session.firstCapture) {
    return null
  }

  return (
    <div className={styles.wrapper}>
      <div className={styles.sidebar}>
        <div className={styles.sidebarContent}>
          {activeCaptureId && (
            <div className={styles.sidebarSection}>
              <span className={styles.title}>Capture #{activeCaptureId}</span>
              <CaptureDetails activeCaptureId={activeCaptureId} />
            </div>
          )}
          <div className={styles.sidebarSection}>
            <span className={styles.title}>View settings</span>
            <ThresholdSlider />
            <Checkbox
              id="show-detections"
              label="Show detections"
              checked={showDetections}
              onCheckedChange={setShowDetections}
              theme={CheckboxTheme.Neutral}
            />
          </div>
          {activeCaptureId && (
            <div
              className={styles.sidebarSection}
              style={{
                flexGrow: 1,
                alignItems: 'flex-end',
              }}
            >
              <CaptureNavigation
                activeCaptureId={activeCaptureId}
                captures={captures}
                setActiveCaptureId={(captureId) => {
                  const capture = captures.find((c) => c.id === captureId)
                  if (capture) {
                    setActiveCapture(capture)
                  }
                }}
              />
            </div>
          )}
        </div>
      </div>
      <Frame
        src={activeCapture?.src}
        width={activeCapture?.width ?? session.firstCapture.width}
        height={activeCapture?.height ?? session.firstCapture.height}
        detections={activeCapture?.detections ?? []}
        showDetections={showDetections}
        threshold={threshold}
      />
      <div className={styles.bottomBar}>
        <SessionCapturesSlider
          session={session}
          activeCapture={activeCapture}
        />
      </div>
    </div>
  )
}

const SessionCapturesSlider = ({
  session,
  activeCapture,
}: {
  session: SessionDetails
  activeCapture?: Capture
}) => {
  const valueLabel = activeCapture?.timeLabel

  const value = activeCapture
    ? ((activeCapture.date.getTime() - session.startDate.getTime()) /
        (session.endDate.getTime() - session.startDate.getTime())) *
      100
    : 0

  return (
    <TimestampSlider
      labels={[
        getFormatedTimeString({ date: session.startDate }),
        getFormatedTimeString({ date: session.endDate }),
      ]}
      value={value}
      valueLabel={valueLabel}
      onValueChange={() => {
        /* TODO: Update capture */
      }}
    />
  )
}
