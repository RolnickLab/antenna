import { useStarCapture } from 'data-services/hooks/captures/useStarCapture'
import { usePipelines } from 'data-services/hooks/pipelines/usePipelines'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { CaptureDetails as Capture } from 'data-services/models/capture-details'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { Select, SelectTheme } from 'design-system/components/select/select'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import styles from './capture-details.module.scss'
import { CaptureInfo } from './capture-info/capture-info'
import { CaptureJob } from './capture-job/capture-job'

export const CaptureDetails = ({
  capture,
  captureId,
}: {
  capture?: Capture
  captureId: string
}) => {
  const [showJobControls, setShowJobControls] = useState(false)

  return (
    <>
      <div className={styles.captureInfo}>
        <CaptureInfo capture={capture} />
        <StarButton capture={capture} captureId={captureId} />
        <IconButton
          icon={IconType.ToggleDown}
          iconTransform={showJobControls ? 'rotate(-180deg)' : undefined}
          theme={IconButtonTheme.Neutral}
          onClick={() => setShowJobControls(!showJobControls)}
        />
      </div>
      {showJobControls && <JobControls capture={capture} />}
    </>
  )
}

const JobControls = ({ capture }: { capture?: Capture }) => {
  const [selectedPipelineId, setSelectedPipelineId] = useState<string>()

  return (
    <div className={styles.jobControls}>
      <div className={styles.pipelinesPickerContainer}>
        <PipelinesPicker
          value={selectedPipelineId}
          onValueChange={setSelectedPipelineId}
        />
      </div>
      <CaptureJob capture={capture} pipelineId={selectedPipelineId} />
    </div>
  )
}

const PipelinesPicker = ({
  value,
  onValueChange,
}: {
  value?: string
  onValueChange: (value?: string) => void
}) => {
  const { projectId } = useParams()
  const { pipelines = [], isLoading } = usePipelines({
    projectId: projectId as string,
  })

  return (
    <Select
      loading={isLoading}
      options={pipelines.map((p) => ({
        value: p.id,
        label: p.name,
      }))}
      placeholder="Pipeline"
      showClear={false}
      theme={SelectTheme.NeutralCompact}
      value={value}
      onValueChange={onValueChange}
    />
  )
}

export const StarButton = ({
  capture,
  captureFetching,
  captureId,
}: {
  capture?: Capture
  captureFetching?: boolean
  captureId: string
}) => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)
  const isStarred = capture?.isStarred ?? false
  const { starCapture, isLoading } = useStarCapture(captureId, isStarred)
  const tooltipContent = project?.canUpdate
    ? isStarred
      ? translate(STRING.STARRED)
      : translate(STRING.STAR)
    : translate(STRING.MESSAGE_PERMISSIONS_MISSING)

  return (
    <Tooltip content={tooltipContent}>
      <IconButton
        icon={isStarred ? IconType.HeartFilled : IconType.Heart}
        disabled={!project?.canUpdate}
        loading={isLoading || captureFetching}
        theme={IconButtonTheme.Neutral}
        onClick={() => starCapture()}
      />
    </Tooltip>
  )
}
