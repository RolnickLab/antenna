import { LicenseInfo } from 'components/license-info/license-info'
import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import { useSessionTimeline } from 'data-services/hooks/sessions/useSessionTimeline'
import { SessionDetails } from 'data-services/models/session-details'
import {
  Checkbox,
  CheckboxTheme,
} from 'design-system/components/checkbox/checkbox'
import { useMemo, useState } from 'react'
import { useUserPreferences } from 'utils/userPreferences/userPreferencesContext'
import { ActivityPlot } from './activity-plot/activity-plot'
import { CaptureDetails } from './capture-details/capture-details'
import { CaptureNavigation } from './capture-navigation/capture-navigation'
import { Frame } from './frame/frame'
import styles from './playback.module.scss'
import { SessionCapturesSlider } from './session-captures-slider/session-captures-slider'
import { ThresholdSlider } from './threshold-slider/threshold-slider'
import { useActiveCaptureId } from './useActiveCapture'

export const Playback = ({ session }: { session: SessionDetails }) => {
  const {
    userPreferences: { scoreThreshold },
  } = useUserPreferences()
  const { timeline = [] } = useSessionTimeline(session.id)
  const [showDetections, setShowDetections] = useState(true)
  const [showDetectionsBelowThreshold, setShowDetectionsBelowThreshold] =
    useState(false)
  const [snapToDetections, setSnapToDetections] = useState(true)
  const { activeCaptureId, setActiveCaptureId } = useActiveCaptureId(
    session.firstCapture?.id
  )
  const { capture: activeCapture } = useCaptureDetails(
    activeCaptureId as string
  )

  const detections = useMemo(() => {
    if (!activeCapture?.detections) {
      return []
    }

    if (showDetectionsBelowThreshold) {
      return activeCapture.detections
    }

    return activeCapture.detections.filter(
      (detection) => detection.score >= scoreThreshold
    )
  }, [activeCapture, scoreThreshold, showDetectionsBelowThreshold])

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
              id="show-detections-below-threshold"
              label="Show detections below threshold"
              checked={showDetectionsBelowThreshold}
              onCheckedChange={setShowDetectionsBelowThreshold}
              theme={CheckboxTheme.Neutral}
            />
            <Checkbox
              id="show-detections"
              label="Show detection frames"
              checked={showDetections}
              onCheckedChange={setShowDetections}
              theme={CheckboxTheme.Neutral}
            />
            <Checkbox
              id="snap-to-detections"
              label="Snap to images with detections"
              checked={snapToDetections}
              onCheckedChange={setSnapToDetections}
              theme={CheckboxTheme.Neutral}
            />
          </div>
        </div>
      </div>
      <Frame
        src={activeCapture?.src}
        width={activeCapture?.width ?? session.firstCapture.width}
        height={activeCapture?.height ?? session.firstCapture.height}
        detections={detections}
        showDetections={showDetections}
        threshold={scoreThreshold}
      />
      <div className={styles.bottomBar}>
        <div className={styles.captureNavigationWrapper}>
          <CaptureNavigation
            activeCapture={activeCapture}
            snapToDetections={snapToDetections}
            timeline={timeline}
            setActiveCaptureId={setActiveCaptureId}
          />
          <div className={styles.licenseInfoWrapper}>
            <LicenseInfo />
          </div>
        </div>
        <div>
          <ActivityPlot
            session={session}
            snapToDetections={snapToDetections}
            timeline={timeline}
            setActiveCaptureId={setActiveCaptureId}
          />
          {timeline.length > 0 && (
            <SessionCapturesSlider
              session={session}
              snapToDetections={snapToDetections}
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
