import { Capture } from 'data-services/models/capture'
import { SessionDetails } from 'data-services/models/session-details'
import { PlaybackSlider } from 'design-system/components/slider/playback-slider'
import { useState } from 'react'
import { useThreshold } from 'utils/threshold/thresholdContext'
import { CaptureJob } from '../capture-job/capture-job'
import { PipelinesPicker } from './pipelines-picker'
import styles from './playback-controls.module.scss'

export const PlaybackControls = ({
  activeCapture,
  session,
}: {
  activeCapture?: Capture
  session: SessionDetails
}) => {
  const [selectedPipeline, setSelectedPipeline] = useState<string>()
  const { defaultThreshold, threshold, setThreshold } = useThreshold()
  const [displayThreshold, setDisplayThreshold] = useState(threshold)

  return (
    <div className={styles.controls}>
      <div className={styles.controlsRow}>
        <PipelinesPicker
          value={selectedPipeline}
          onValueChange={setSelectedPipeline}
        />
        {activeCapture && <CaptureJob captureId={activeCapture.id} />}
      </div>
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
