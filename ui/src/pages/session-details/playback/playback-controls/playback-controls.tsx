import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import { Capture } from 'data-services/models/capture'
import { PlaybackSlider } from 'design-system/components/slider/playback-slider'
import { useState } from 'react'
import { useThreshold } from 'utils/threshold/thresholdContext'
import { CaptureInfo } from '../capture-info/capture-info'
import { CaptureJob } from '../capture-job/capture-job'
import { PipelinesPicker } from './pipelines-picker'
import styles from './playback-controls.module.scss'

export const PlaybackControls = ({
  activeCapture,
}: {
  activeCapture?: Capture
}) => {
  const { defaultThreshold, threshold, setThreshold } = useThreshold()
  const [displayThreshold, setDisplayThreshold] = useState(threshold)

  return (
    <div className={styles.controls}>
      <div className={styles.slider}>
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
      </div>
      {activeCapture?.id && <DetailedControls captureId={activeCapture.id} />}
    </div>
  )
}

const DetailedControls = ({ captureId }: { captureId: string }) => {
  const [selectedPipelineId, setSelectedPipelineId] = useState<string>()
  const { capture } = useCaptureDetails(captureId)

  if (!capture) {
    return null
  }

  return (
    <div className={styles.detailedControls}>
      <CaptureInfo capture={capture} />
      <PipelinesPicker
        value={selectedPipelineId}
        onValueChange={setSelectedPipelineId}
      />
      <CaptureJob capture={capture} pipelineId={selectedPipelineId} />
    </div>
  )
}
