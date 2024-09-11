import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import { useSessionTimeline } from 'data-services/hooks/sessions/useSessionTimeline'
import { SessionDetails } from 'data-services/models/session-details'
import {
  Checkbox,
  CheckboxTheme,
} from 'design-system/components/checkbox/checkbox'
import { useState } from 'react'
import { useUserPreferences } from 'utils/userPreferences/userPreferencesContext'
import { ActivityPlot } from './activity-plot/activity-plot'
import { CaptureDetails } from './capture-details/capture-details'
import { CaptureNavigation } from './capture-navigation/capture-navigation'
import { Frame } from './frame/frame'
import styles from './playback.module.scss'
import { SessionCapturesSlider } from './session-captures-slider/session-captures-slider'
import { ThresholdSlider } from './threshold-slider/threshold-slider'
import { useActiveCaptureId } from './useActiveCapture'
import { LicenseInfo } from 'components/license-info/license-info'

export const Playback = ({ session }: { session: SessionDetails }) => {
  const {
    userPreferences: { scoreThreshold },
  } = useUserPreferences()
  const { timeline = [] } = useSessionTimeline(session.id)
  const [showDetections, setShowDetections] = useState(true)
  const { activeCaptureId, setActiveCaptureId } = useActiveCaptureId(
    session.firstCapture?.id
  )
  const { capture: activeCapture } = useCaptureDetails(
    activeCaptureId as string
  )

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
              <CaptureDetails
                capture={activeCapture}
                captureId={activeCaptureId}
              />
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
        </div>
      </div>
      <Frame
        src={activeCapture?.src}
        width={activeCapture?.width ?? session.firstCapture.width}
        height={activeCapture?.height ?? session.firstCapture.height}
        detections={activeCapture?.detections ?? []}
        showDetections={showDetections}
        threshold={scoreThreshold}
      />
      <div className={styles.bottomBar}>
        <div className={styles.captureNavigationWrapper}>
          <CaptureNavigation
            activeCapture={activeCapture}
            setActiveCaptureId={setActiveCaptureId}
          />
          <div className={styles.licenseInfoWrapper}>
            <LicenseInfo style={{ textAlign: 'right' }} />
          </div>
        </div>
        <div>
          <ActivityPlot
            session={session}
            timeline={timeline}
            setActiveCaptureId={setActiveCaptureId}
          />
          {timeline.length > 0 && (
            <SessionCapturesSlider
              session={session}
              timeline={timeline}
              activeCapture={activeCapture}
              setActiveCaptureId={setActiveCaptureId}
            />
          )}
        </div>
      </div>
    </div>
  )
}
