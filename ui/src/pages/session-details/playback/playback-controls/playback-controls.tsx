import { useCaptureDetails } from 'data-services/hooks/captures/useCaptureDetails'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { PlaybackSlider } from 'design-system/components/slider/playback-slider'
import { useState } from 'react'
import { useThreshold } from 'utils/threshold/thresholdContext'
import { CaptureInfo } from '../capture-info/capture-info'
import { CaptureJob } from '../capture-job/capture-job'
import { useActiveCaptureId } from '../useActiveCapture'
import { PipelinesPicker } from './pipelines-picker'
import styles from './playback-controls.module.scss'

export const PlaybackControls = () => {
  const { activeCaptureId } = useActiveCaptureId()
  const { defaultThreshold, threshold, setThreshold } = useThreshold()
  const [showDetails, setShowDetails] = useState(false)
  const [displayThreshold, setDisplayThreshold] = useState(threshold)

  return (
    <div className={styles.controls}>
      <div className={styles.sliderControls}>
        <IconButton
          icon={IconType.ToggleDown}
          iconTransform={showDetails ? 'rotate(-180deg)' : undefined}
          theme={IconButtonTheme.Neutral}
          onClick={() => setShowDetails(!showDetails)}
        />
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
      {activeCaptureId && showDetails && (
        <DetailedControls captureId={activeCaptureId} />
      )}
    </div>
  )
}

const DetailedControls = ({ captureId }: { captureId: string }) => {
  const [selectedPipelineId, setSelectedPipelineId] = useState<string>()
  const { capture } = useCaptureDetails(captureId)

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
