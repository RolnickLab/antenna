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
import { STRING, translate } from 'utils/language'
import { JobStageLabel } from './job-stage-label/job-stage-label'
import styles from './styles.module.scss'

export const JobDetails = ({ job, title }: { job: Job; title: string }) => (
  <>
    <Dialog.Header title={title}>
      <div className={styles.buttonWrapper}>
        {/* Room for action buttons */}
      </div>
    </Dialog.Header>
    <div className={styles.content}>
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Summary</h2>
        <div className={styles.sectionContent}>
          <JobSummary job={job} />
        </div>
      </div>
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Stages</h2>
        <JobStages job={job} />
      </div>
    </div>
  </>
)

const JobSummary = ({ job }: { job: Job }) => {
  const status = (() => {
    switch (job.status) {
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
    <>
      <div className={styles.sectionFields}>
        <div className={styles.sectionStatus}>
          <InputContent label={translate(STRING.TABLE_COLUMN_STATUS)}>
            <StatusBar
              status={status}
              progress={job.statusValue}
              description={job.statusDetails}
            />
          </InputContent>
        </div>
        <InputValue label={translate(STRING.TABLE_COLUMN_ID)} value={job.id} />
        <InputValue label="Name" value={job.name} />
        <InputValue
          label={translate(STRING.TABLE_COLUMN_PROJECT)}
          value={job.project}
        />
        <InputValue label={job.inputLabel} value={job.inputValue} />
        <InputValue label="Started at" value={job.startedAt} />
        <InputValue label="Finished at" value={job.finishedAt} />
      </div>
    </>
  )
}

const JobStages = ({ job }: { job: Job }) => (
  <Wizard.Root>
    {job.stages.map((stage, index) => {
      const stageInfo = job.getStageInfo(stage.key)

      if (!stageInfo) {
        return null
      }

      const status = (() => {
        switch (stageInfo.status) {
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
            <JobStageLabel label={stageInfo.statusLabel} status={status} />
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
                theme={StatusBulletTheme.Neutral}
              />
            )}
          </Wizard.Trigger>
          <Wizard.Content>
            <div className={styles.sectionFields}>
              {stageInfo.fields.map((field) => (
                <InputValue
                  key={field.key}
                  label={field.label}
                  value={field.value}
                />
              ))}
            </div>
          </Wizard.Content>
        </Wizard.Item>
      )
    })}
  </Wizard.Root>
)
