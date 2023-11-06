import { Capture } from 'data-services/models/capture'
import { SessionDetails } from 'data-services/models/session-details'
import { PlaybackSlider } from 'design-system/components/slider/playback-slider'
import { useState } from 'react'
import { useThreshold } from 'utils/threshold/thresholdContext'
import { CaptureJob } from '../capture-job/capture-job'
import styles from './playback-controls.module.scss'

export const PlaybackControls = ({
  activeCapture,
  session,
}: {
  activeCapture: Capture
  session: SessionDetails
}) => {
  const { defaultThreshold, threshold, setThreshold } = useThreshold()
  const [displayThreshold, setDisplayThreshold] = useState(threshold)

  return (
    <div className={styles.controls}>
      <CaptureJob captureId={activeCapture.id} />
      <div className={styles.slider}>
        {session.numDetections && session.numDetections > 0 ? (
          <PlaybackSlider
            defaultValue={defaultThreshold}
            label="Score"
            value={displayThreshold}
            onValueChange={setDisplayThreshold}
            onValueCommit={(value) => {
              setDisplayThreshold(value)
              setThreshold(value)
            }}
          />
        ) : null}
      </div>
    </div>
  )
}
