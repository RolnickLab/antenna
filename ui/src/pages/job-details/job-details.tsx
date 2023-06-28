import { Job } from 'data-services/models/job'
import { Button } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
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
        <Button
          label={translate(STRING.CANCEL)}
          onClick={onCancelClick}
          type="button"
        />
      </div>
    </Dialog.Header>
    <div className={styles.content}></div>
  </>
)
