import classNames from 'classnames'
import { useStarCapture } from 'data-services/hooks/captures/useStarCapture'
import { usePipelines } from 'data-services/hooks/pipelines/usePipelines'
import { useProjectDetails } from 'data-services/hooks/projects/useProjectDetails'
import { CaptureDetails as Capture } from 'data-services/models/capture-details'
import { Job } from 'data-services/models/job'
import { ProcessingService } from 'data-services/models/processing-service'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { ExternalLinkIcon, HeartIcon, Loader2Icon } from 'lucide-react'
import { Button, buttonVariants, Select } from 'nova-ui-kit'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { useUser } from 'utils/user/userContext'
import styles from './capture-details.module.scss'
import { CaptureJobDialog } from './capture-job/capture-job-dialog'
import { ProcessNow } from './capture-job/process-now'

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
          <StarButton
            capture={capture}
            captureId={captureId}
            canStar={capture.canStar}
          />
        )}
        <a
          href={capture.url}
          className={classNames(
            buttonVariants({ size: 'icon' }),
            'rounded-md !bg-neutral-700 text-neutral-200'
          )}
          rel="noreferrer"
          target="_blank"
        >
          <ExternalLinkIcon className="w-4 h-4" />
        </a>
      </div>
      <div className={styles.infoWrapper}>
        <div className="flex items-start gap-8">
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
        </div>
        {user.loggedIn ? (
          <div>
            <span className={styles.label}>
              {translate(STRING.FIELD_LABEL_PROCESS)}
            </span>
            <JobControls capture={capture} />
          </div>
        ) : null}
        {user.loggedIn && capture.currentJob ? (
          <div>
            <span className={styles.label}>Latest job status</span>
            <JobDetails job={capture.currentJob} />
          </div>
        ) : null}
        <div className="flex items-start gap-8">
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
            <span
              className={classNames(styles.value, styles.bubble)}
              style={{ backgroundColor: 'transparent', border: 'none' }}
            >
              {capture.numTaxa}
            </span>
          </div>
        </div>
      </div>
    </>
  )
}

const StarButton = ({
  capture,
  captureFetching,
  captureId,
  canStar,
}: {
  capture?: Capture
  captureFetching?: boolean
  captureId: string
  canStar: boolean
}) => {
  const isStarred = capture?.isStarred ?? false
  const { starCapture, isLoading } = useStarCapture(captureId, isStarred)
  const tooltipContent = canStar
    ? isStarred
      ? translate(STRING.STARRED)
      : translate(STRING.STAR)
    : translate(STRING.MESSAGE_PERMISSIONS_MISSING)

  return (
    <BasicTooltip asChild content={tooltipContent}>
      <Button
        className="rounded-md !bg-neutral-700 text-neutral-200"
        disabled={!canStar}
        size="icon"
        onClick={() => starCapture()}
      >
        {isLoading || captureFetching ? (
          <Loader2Icon className="w-4 h-4 animate-spin" />
        ) : (
          <HeartIcon
            className="w-4 h-4 transition-colors"
            fill={isStarred ? 'currentColor' : 'transparent'}
          />
        )}
      </Button>
    </BasicTooltip>
  )
}

const JobControls = ({ capture }: { capture?: Capture }) => {
  const { projectId } = useParams()
  const { project } = useProjectDetails(projectId as string, true)
  const [selectedPipelineId, setSelectedPipelineId] = useState(
    project?.settings.defaultProcessingPipeline?.id
  )

  return (
    <div className={styles.jobControls}>
      <PipelinesPicker
        value={selectedPipelineId}
        onValueChange={setSelectedPipelineId}
      />
      <ProcessNow capture={capture} pipelineId={selectedPipelineId} />
    </div>
  )
}

const JobDetails = ({ job }: { job: Job }) => (
  <div className="flex items-center justify-between gap-4">
    <div className="flex items-center gap-2">
      <div
        className="w-2 h-2 rounded-full"
        style={{ backgroundColor: job.status.color }}
      />
      <span className={classNames(styles.value, 'pt-0.5')}>
        {job.status.label}
      </span>
    </div>
    <CaptureJobDialog id={job.id} />
  </div>
)

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
    <Select.Root
      disabled={pipelines.length === 0}
      onValueChange={onValueChange}
      value={value ?? ''}
    >
      <Select.Trigger
        className="h-8 !bg-neutral-700 border-none text-neutral-200 body-small focus:ring-0 focus:ring-offset-0"
        loading={isLoading}
      >
        <Select.Value placeholder="Select a pipeline" />
      </Select.Trigger>
      <Select.Content>
        {pipelines.map((p) => (
          <Select.Item
            className="h-8 body-small"
            key={p.name}
            value={String(p.id)}
            disabled={!p.currentProcessingService.online}
          >
            <div className="flex items-center gap-4">
              <div
                className="w-2 h-2 rounded-full mb-0.5 shrink-0"
                style={{
                  backgroundColor: p.currentProcessingService.service
                    ? p.currentProcessingService.service?.status.color
                    : ProcessingService.getStatusInfo('OFFLINE').color,
                }}
              />
              <span className="whitespace-nowrap text-ellipsis overflow-hidden">
                {p.name}
              </span>
            </div>
          </Select.Item>
        ))}
      </Select.Content>
    </Select.Root>
  )
}
