import { FetchInfo } from 'components/fetch-info/fetch-info'
import { FormRow, FormSection } from 'components/form/layout/layout'
import { JobStatus } from 'data-services/models/job'
import { JobDetails as Job } from 'data-services/models/job-details'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { InputContent, InputValue } from 'design-system/components/input/input'
import { StatusBar } from 'design-system/components/status/status-bar/status-bar'
import { Status } from 'design-system/components/status/types'
import {
  StatusBullet,
  StatusBulletTheme,
} from 'design-system/components/wizard/status-bullet/status-bullet'
import * as Wizard from 'design-system/components/wizard/wizard'
import { DeleteJobsDialog } from 'pages/jobs/delete-jobs-dialog'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { STRING, translate } from 'utils/language'
import { CancelJob } from './job-actions/cancel-job'
import { QueueJob } from './job-actions/queue-job'
import styles from './job-details.module.scss'
import { JobStageLabel } from './job-stage-label/job-stage-label'

export const JobDetails = ({
  job,
  title,
  isFetching,
  onDelete,
}: {
  job: Job
  title: string
  isFetching?: boolean
  onDelete: () => void
}) => (
  <>
    <Dialog.Header title={title}>
      <div className={styles.headerContent}>
        <div className={styles.fetchInfoWrapper}>
          {isFetching ? <FetchInfo /> : null}
        </div>
        {job.canQueue && <QueueJob jobId={job.id} />}
        {job.canCancel && <CancelJob jobId={job.id} />}
        {job.canDelete && <DeleteJobsDialog id={job.id} onDelete={onDelete} />}
      </div>
    </Dialog.Header>
    <div className={styles.content}>
      <FormSection title={translate(STRING.SUMMARY)}>
        <JobSummary job={job} />
      </FormSection>
      <FormSection title={translate(STRING.STAGES)}>
        <JobStages job={job} />
      </FormSection>
    </div>
  </>
)

const JobSummary = ({ job }: { job: Job }) => {
  const { projectId } = useParams()

  const status = (() => {
    switch (job.status) {
      case JobStatus.Created:
        return Status.Neutral
      case JobStatus.Pending:
        return Status.Warning
      case JobStatus.Started:
        return Status.Warning
      case JobStatus.Success:
        return Status.Success
      case JobStatus.Canceling:
        return Status.Warning
      case JobStatus.Revoked:
        return Status.Error
      default:
        return Status.Error
    }
  })()

  return (
    <>
      <FormRow>
        <div className={styles.status}>
          <InputContent label={translate(STRING.FIELD_LABEL_STATUS)}>
            <StatusBar
              status={status}
              progress={job.statusValue}
              description={job.statusDetails}
            />
          </InputContent>
        </div>
      </FormRow>
      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_NAME)}
          value={job.name}
        />
        <InputValue
          label={translate(STRING.FIELD_LABEL_DELAY)}
          value={job.delay}
        />
      </FormRow>
      <FormRow>
        {job.sourceImages ? (
          <InputValue
            label={translate(STRING.FIELD_LABEL_SOURCE_IMAGES)}
            to={APP_ROUTES.COLLECTION_DETAILS({
              projectId: projectId as string,
              collectionId: job.sourceImages.id,
            })}
            value={job.sourceImages.name}
          />
        ) : job.sourceImage ? (
          <InputValue
            label={translate(STRING.FIELD_LABEL_SOURCE_IMAGE)}
            value={`Capture #${job.sourceImage.id}`}
          />
        ) : null}

        <InputValue
          label={translate(STRING.FIELD_LABEL_PIPELINE)}
          value={job.pipeline?.name}
        />
      </FormRow>
      <FormRow>
        <InputValue
          label={translate(STRING.FIELD_LABEL_STARTED_AT)}
          value={job.startedAt}
        />
        <InputValue
          label={translate(STRING.FIELD_LABEL_FINISHED_AT)}
          value={job.finishedAt}
        />
      </FormRow>
    </>
  )
}

const JobStages = ({ job }: { job: Job }) => {
  const [activeStage, setActiveStage] = useState<string>()

  return (
    <Wizard.Root value={activeStage} onValueChange={setActiveStage}>
      {job.stages.map((stage, index) => {
        const stageInfo = job.getStageInfo(stage.key)

        if (!stageInfo) {
          return null
        }

        const isOpen = activeStage === stage.key

        const status = (() => {
          switch (stageInfo.status) {
            case JobStatus.Created:
              return Status.Neutral
            case JobStatus.Pending:
              return Status.Neutral
            case JobStatus.Started:
              return Status.Warning
            case JobStatus.Success:
              return Status.Success
            default:
              return Status.Error
          }
        })()

        return (
          <Wizard.Item key={stage.key} value={stage.key}>
            <div className={styles.jobStageLabel}>
              <JobStageLabel
                label={stageInfo.statusLabel}
                status={status}
                statusDetails={job.statusDetails}
              />
            </div>
            <Wizard.Trigger title={stageInfo.name}>
              {status === Status.Success ? (
                <StatusBullet
                  icon={IconType.Checkmark}
                  theme={StatusBulletTheme.Success}
                />
              ) : (
                <StatusBullet
                  value={index + 1}
                  theme={
                    isOpen
                      ? StatusBulletTheme.Default
                      : StatusBulletTheme.Neutral
                  }
                />
              )}
            </Wizard.Trigger>
            <Wizard.Content>
              <FormRow>
                {stageInfo.fields.map((field) => (
                  <InputValue
                    key={field.key}
                    label={field.label}
                    value={field.value}
                  />
                ))}
              </FormRow>
            </Wizard.Content>
          </Wizard.Item>
        )
      })}
    </Wizard.Root>
  )
}
