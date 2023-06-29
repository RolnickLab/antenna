import { Job } from 'data-services/models/job'
import { Button } from 'design-system/components/button/button'
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
import styles from './styles.module.scss'

export const JobDetails = ({
  job,
  title,
  onCancelClick,
}: {
  job: Job
  title: string
  onCancelClick: () => void
}) => (
  <>
    <Dialog.Header title={title}>
      <div className={styles.buttonWrapper}>
        <Button label={translate(STRING.CANCEL)} onClick={onCancelClick} />
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
        <JobStages />
      </div>
    </div>
  </>
)

const JobSummary = ({ job }: { job: Job }) => (
  <div className={styles.sectionColumn}>
    <InputContent label={translate(STRING.TABLE_COLUMN_STATUS)}>
      <StatusBar
        status={Status.Success}
        progress={0.33}
        description="33% completed, 3h 10min left."
      />
    </InputContent>
    <div className={styles.sectionRow}>
      <InputValue
        label={translate(STRING.TABLE_COLUMN_ID)}
        value={job.idLabel}
      />
      <InputValue
        label={translate(STRING.TABLE_COLUMN_DESCRIPTION)}
        value={job.description}
      />
    </div>
    <div className={styles.sectionRow}>
      <InputValue
        label={translate(STRING.TABLE_COLUMN_PROJECT)}
        value={job.project}
      />
      <InputValue
        label={translate(STRING.TABLE_COLUMN_IMAGES)}
        value={job.totalImages}
      />
    </div>
    <div className={styles.sectionRow}>
      <InputValue
        label={translate(STRING.TABLE_COLUMN_JOB_STARTED)}
        value={job.jobStarted}
      />
      <InputValue label="Estimated time" value="WIP" />
    </div>
    <InputValue label="Models" value={`WIP\nWIP\nWIP`} />
  </div>
)

const JobStages = () => (
  <Wizard.Root>
    <Wizard.Item value="stage-1">
      <Wizard.Trigger title="Object Detection">
        <StatusBullet
          icon={IconType.Checkmark}
          theme={StatusBulletTheme.Success}
        />
      </Wizard.Trigger>
      <Wizard.Content>
        <div className={styles.sectionColumn}>
          <div className={styles.sectionRow}>
            <InputValue label="Localization model" value="WIP" />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_BATCH_SIZE)}
              value="WIP"
            />
          </div>
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_IMAGES_PROCESSED)}
              value="WIP"
            />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_ITEMS_DETECTED)}
              value="WIP"
            />
          </div>
        </div>
      </Wizard.Content>
    </Wizard.Item>

    <Wizard.Item value="stage-2">
      <Wizard.Trigger title="Objects of Interest Filter">
        <StatusBullet value={2} theme={StatusBulletTheme.Default} />
      </Wizard.Trigger>
      <Wizard.Content>
        <div className={styles.sectionColumn}>
          <div className={styles.sectionRow}>
            <InputValue label="Binary classification model" value="WIP" />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_BATCH_SIZE)}
              value="WIP"
            />
          </div>
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_IMAGES_PROCESSED)}
              value="WIP"
            />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_ITEMS_DETECTED)}
              value="WIP"
            />
          </div>
        </div>
      </Wizard.Content>
    </Wizard.Item>

    <Wizard.Item value="stage-3">
      <Wizard.Trigger title="Taxon Classifier">
        <StatusBullet value={3} theme={StatusBulletTheme.Neutral} />
      </Wizard.Trigger>
      <Wizard.Content>
        <div className={styles.sectionColumn}>
          <div className={styles.sectionRow}>
            <InputValue label="Species classification model" value="WIP" />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_BATCH_SIZE)}
              value="WIP"
            />
          </div>
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_IMAGES_PROCESSED)}
              value="WIP"
            />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_ITEMS_DETECTED)}
              value="WIP"
            />
          </div>
        </div>
      </Wizard.Content>
    </Wizard.Item>

    <Wizard.Item value="stage-4">
      <Wizard.Trigger title="Occurrence Tracking">
        <StatusBullet value={4} theme={StatusBulletTheme.Neutral} />
      </Wizard.Trigger>
      <Wizard.Content>
        <div className={styles.sectionColumn}>
          <div className={styles.sectionRow}>
            <InputValue label="Occurrence tracking algorithm" value="WIP" />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_BATCH_SIZE)}
              value="WIP"
            />
          </div>
          <div className={styles.sectionRow}>
            <InputValue
              label={translate(STRING.DETAILS_LABEL_IMAGES_PROCESSED)}
              value="WIP"
            />
            <InputValue
              label={translate(STRING.DETAILS_LABEL_ITEMS_DETECTED)}
              value="WIP"
            />
          </div>
        </div>
      </Wizard.Content>
    </Wizard.Item>
  </Wizard.Root>
)
