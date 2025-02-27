import { LicenseInfo } from 'components/license-info/license-info'
import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import { useSessionTimeline } from 'data-services/hooks/sessions/useSessionTimeline'
import { SessionDetails } from 'data-services/models/session-details'
import {
  Checkbox,
  CheckboxTheme,
} from 'design-system/components/checkbox/checkbox'
import { useEffect, useMemo, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { useUserPreferences } from 'utils/userPreferences/userPreferencesContext'
import { ActivityPlot } from './activity-plot/lazy-activity-plot'
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
  const [poll, setPoll] = useState(false)
  const [showDetections, setShowDetections] = useState(true)
  const [showDetectionsBelowThreshold, setShowDetectionsBelowThreshold] =
    useState(false)
  const [snapToDetections, setSnapToDetections] = useState(
    session.numDetections ? true : false
  )
  const { activeCaptureId, setActiveCaptureId } = useActiveCaptureId(
    session.firstCapture?.id
  )
  const { capture: activeCapture } = useCaptureDetails(
    activeCaptureId as string,
    poll
  )

  useEffect(() => {
    // When the active capture has a job in progress, we want to poll the endpoint so we can show any updates from the job
    if (activeCapture?.hasJobInProgress) {
      setPoll(true)
    } else {
      setPoll(false)
    }
  }, [activeCapture])

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
            <div>
              <span className={styles.label}>
                {translate(STRING.FIELD_LABEL_SCORE_THRESHOLD)}
              </span>
              <ThresholdSlider />
            </div>
            <span className={styles.label}>Preferences</span>
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
              disabled={session.numDetections ? false : true}
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
