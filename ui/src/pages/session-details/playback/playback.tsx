import { useInfiniteCaptures } from 'data-services/hooks/sessions/useInfiniteCaptures'
import { SessionDetails } from 'data-services/models/session-details'
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
    threshold
  )
  const { activeCapture, setActiveCapture } = useActiveCapture(captures)
  const [showOverlay, setShowOverlay] = useState(false)
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
      <div
        onMouseOver={() => setShowOverlay(true)}
        onMouseOut={() => setShowOverlay(false)}
      >
        <Frame
          src={activeCapture?.src}
          width={activeCapture?.width ?? session.firstCapture.width}
          height={activeCapture?.height ?? session.firstCapture.height}
          detections={activeCapture?.detections ?? []}
          showOverlay={showOverlay}
        />
      </div>
      <div className={styles.bottomBar}>
        <SessionSlider session={session} />
      </div>
    </div>
  )
}

const SessionSlider = ({ session }: { session: SessionDetails }) => {
  const [value, setValue] = useState<number>(0)

  return (
    <TimestampSlider
      labels={[
        getFormatedTimeString({ date: session.endDate }),
        getFormatedTimeString({ date: session.startDate }),
      ]}
      value={value}
      onValueChange={setValue}
    />
  )
}
