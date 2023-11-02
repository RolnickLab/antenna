import { useCreateJob } from 'data-services/hooks/jobs/useCreateJob'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import * as Dialog from 'design-system/components/dialog/dialog'
import { IconType } from 'design-system/components/icon/icon'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { JobDetailsForm } from './job-details-form/job-details-form'
import styles from './job-details.module.scss'

const CLOSE_TIMEOUT = 1000

export const NewJobDialog = () => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const { createJob, isLoading, isSuccess, error } = useCreateJob(() =>
    setTimeout(() => {
      setIsOpen(false)
    }, CLOSE_TIMEOUT)
  )

  const label = translate(STRING.ENTITY_CREATE, {
    type: translate(STRING.ENTITY_TYPE_JOB),
  })

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <Button
          label={label}
          icon={IconType.Plus}
          theme={ButtonTheme.Default}
        />
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <Dialog.Header title={label} />
        <div className={styles.content}>
          <JobDetailsForm
            error={error}
            isLoading={isLoading}
            isSuccess={isSuccess}
            onSubmit={(data) => {
              createJob({
                ...data,
                projectId: projectId as string,
              })
            }}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
