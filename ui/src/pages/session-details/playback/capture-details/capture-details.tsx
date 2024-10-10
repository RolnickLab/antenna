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
import { useUser } from 'utils/user/userContext'
import styles from './capture-details.module.scss'
import { CaptureJob } from './capture-job/capture-job'

export const CaptureDetails = ({
  capture,
  captureId,
}: {
  capture?: Capture
  captureId: string
}) => {
  const { user } = useUser()

  if (!capture) {
    return null
  }

  return (
    <>
      <div className={styles.starButtonWrapper}>
        {user.loggedIn && (
          <StarButton capture={capture} captureId={captureId} />
        )}
        <a
          href={capture.url}
          className={styles.link}
          rel="noreferrer"
          target="_blank"
          tabIndex={-1}
        >
          <IconButton
            icon={IconType.ExternalLink}
            theme={IconButtonTheme.Neutral}
          />
        </a>
      </div>
      <div className={styles.infoWrapper}>
        <div>
          <span className={styles.label}>
            {translate(STRING.FIELD_LABEL_TIMESTAMP)}
          </span>
          <span className={styles.value}>{capture.dateTimeLabel}</span>
        </div>
        <div>
          <span className={styles.label}>
            {translate(STRING.FIELD_LABEL_DETECTIONS)}
          </span>
          <span className={styles.value}>{capture.numDetections}</span>
        </div>
        <div>
          <span className={styles.label}>
            {translate(STRING.FIELD_LABEL_SIZE)}
          </span>
          <span className={styles.value}>{capture.sizeLabel}</span>
        </div>
        {user.loggedIn && (
          <div>
            <span className={styles.label}>
              {translate(STRING.FIELD_LABEL_PROCESS)}
            </span>
            <JobControls capture={capture} />
          </div>
        )}
      </div>
    </>
  )
}

const StarButton = ({
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
        value: String(p.id),
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
