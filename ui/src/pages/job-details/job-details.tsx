import { FetchInfo } from 'components/fetch-info/fetch-info'
import { FormRow, FormSection } from 'components/form/layout/layout'
import { Export } from 'data-services/models/export'
import { JobStatusType } from 'data-services/models/job'
import { JobDetails as Job } from 'data-services/models/job-details'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { InputContent, InputValue } from 'design-system/components/input/input'
import { StatusBar } from 'design-system/components/status/status-bar'
import {
  StatusBullet,
  StatusBulletTheme,
} from 'design-system/components/wizard/status-bullet/status-bullet'
import * as Wizard from 'design-system/components/wizard/wizard'
import { CodeBlock } from 'nova-ui-kit'
import { DeleteJobsDialog } from 'pages/jobs/delete-jobs-dialog'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import { CancelJob } from './job-actions/cancel-job'
import { QueueJob } from './job-actions/queue-job'
import { RetryJob } from './job-actions/retry-job'
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
        {job.canRetry && <RetryJob jobId={job.id} />}
        {job.canDelete && <DeleteJobsDialog id={job.id} onDelete={onDelete} />}
      </div>
    </Dialog.Header>
    <div className={styles.content}>
      <FormSection title={translate(STRING.SUMMARY)}>
        <JobSummary job={job} />
      </FormSection>
      {job.stages.length > 0 && (
        <FormSection title={translate(STRING.STAGES)}>
          <JobStages job={job} />
        </FormSection>
      )}
    </div>
  </>
)

const JobSummary = ({ job }: { job: Job }) => {
  const { projectId } = useParams()

  return (
    <>
      <FormRow>
        <div className={styles.status}>
          <InputContent label={translate(STRING.FIELD_LABEL_STATUS)}>
            <StatusBar color={job.status.color} progress={job.progress.value} />
          </InputContent>
        </div>
        <InputValue
          label={translate(STRING.FIELD_LABEL_NAME)}
          value={job.name}
        />
        <InputValue
          label={translate(STRING.FIELD_LABEL_TYPE)}
          value={job.type.label}
        />
        {job.delay ? (
          <InputValue
            label={translate(STRING.FIELD_LABEL_DELAY)}
            value={job.delay}
          />
        ) : null}
        {job.export ? (
          <InputValue
            label="Export"
            value={Export.getExportTypeInfo(job.export.format as any).label}
            to={APP_ROUTES.EXPORT_DETAILS({
              projectId: projectId as string,
              exportId: job.export.id,
            })}
          />
        ) : null}
        {job.deployment ? (
          <InputValue
            label={translate(STRING.FIELD_LABEL_DEPLOYMENT)}
            value={job.deployment.name}
            to={APP_ROUTES.DEPLOYMENT_DETAILS({
              projectId: projectId as string,
              deploymentId: job.deployment.id,
            })}
          />
        ) : null}
        {job.pipeline ? (
          <InputValue
            label={translate(STRING.FIELD_LABEL_PIPELINE)}
            value={job.pipeline.name}
          />
        ) : null}
        {job.sourceImage ? (
          <InputValue
            label={translate(STRING.FIELD_LABEL_SOURCE_IMAGE)}
            value={job.sourceImage.label}
            to={
              job.sourceImage.sessionId
                ? getAppRoute({
                    to: APP_ROUTES.SESSION_DETAILS({
                      projectId: projectId as string,
                      sessionId: job.sourceImage.sessionId,
                    }),
                    filters: {
                      capture: job.sourceImage.id,
                    },
                  })
                : undefined
            }
          />
        ) : job.sourceImages ? (
          <InputValue
            label={translate(STRING.FIELD_LABEL_CAPTURE_SET)}
            value={job.sourceImages?.name}
          />
        ) : null}
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
        <InputValue
          label={translate(STRING.FIELD_LABEL_CREATED_AT)}
          value={job.createdAt}
        />
        <InputValue
          label={translate(STRING.FIELD_LABEL_UPDATED_AT)}
          value={job.updatedAt}
        />
      </FormRow>
      {job.logs.length > 0 && (
        <FormRow>
          <InputContent
            label={translate(STRING.FIELD_LABEL_LOGS)}
            style={{ gridColumn: 'span 2' }}
          >
            <CodeBlock collapsible snippet={job.logs.join('\n')} />
          </InputContent>
        </FormRow>
      )}
      {job.errors.length > 0 && (
        <FormRow>
          <InputContent
            label={translate(STRING.FIELD_LABEL_ERRORS)}
            style={{ gridColumn: 'span 2' }}
          >
            <CodeBlock
              collapsible
              snippet={job.errors.join('\n')}
              theme="error"
            />
          </InputContent>
        </FormRow>
      )}
    </>
  )
}

const JobStages = ({ job }: { job: Job }) => {
  const [activeStage, setActiveStage] = useState<string>()

  return (
    <Wizard.Root value={activeStage} onValueChange={setActiveStage}>
      {job.stages.map((stage, index) => {
        const isOpen = activeStage === stage.key

        return (
          <Wizard.Item key={stage.key} value={stage.key}>
            <div className={styles.jobStageLabel}>
              <JobStageLabel
                details={stage.details}
                label={stage.status.label}
                color={stage.status.color}
              />
            </div>
            <Wizard.Trigger title={stage.name}>
              {stage.status.type === JobStatusType.Success ? (
                <StatusBullet
                  icon={IconType.RadixCheck}
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
                {stage.fields.map((field) => (
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
