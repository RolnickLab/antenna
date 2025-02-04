import classNames from 'classnames'
import { useStarCapture } from 'data-services/hooks/captures/useStarCapture'
import { usePipelines } from 'data-services/hooks/pipelines/usePipelines'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { CaptureDetails as Capture } from 'data-services/models/capture-details'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { Select } from 'nova-ui-kit'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
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
  const { projectId } = useParams()

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
        <div>
          <span className={styles.label}>
            {translate(STRING.FIELD_LABEL_JOBS)}
          </span>
          <Link
            to={getAppRoute({
              to: APP_ROUTES.JOBS({
                projectId: projectId as string,
              }),
              filters: {
                source_image_single: capture.id,
              },
            })}
          >
            <span className={classNames(styles.value, styles.bubble)}>
              {capture.numJobs}
            </span>
          </Link>
        </div>
        <div>
          <span className={styles.label}>
            {translate(STRING.FIELD_LABEL_OCCURRENCES)}
          </span>
          <Link
            to={getAppRoute({
              to: APP_ROUTES.OCCURRENCES({
                projectId: projectId as string,
              }),
              filters: {
                detections__source_image: capture.id,
              },
            })}
          >
            <span className={classNames(styles.value, styles.bubble)}>
              {capture.numOccurrences}
            </span>
          </Link>
        </div>
        <div>
          <span className={styles.label}>
            {translate(STRING.FIELD_LABEL_TAXA)}
          </span>
          <span className={styles.value}>{capture.numTaxa}</span>
        </div>
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
  const { pipelines = [] } = usePipelines({
    projectId: projectId as string,
  })

  return (
    <Select.Root value={value ?? ''} onValueChange={onValueChange}>
      <Select.Trigger>
        <Select.Value placeholder="Select a value" />
      </Select.Trigger>
      <Select.Content>
        {pipelines.map((p) => (
          <Select.Item
            key={p.name}
            value={String(p.id)}
            disabled={!p.hasOnlineProcessingService.online}
          >
            <span className="flex items-center gap-2">
              <span
                className="w-3 h-3 rounded-full mb-0.5"
                style={{
                  backgroundColor:
                    p.hasOnlineProcessingService.service.status.color,
                }}
              />
              <span>{p.name}</span>
            </span>
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
