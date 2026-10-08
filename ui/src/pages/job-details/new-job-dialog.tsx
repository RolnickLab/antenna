import { useCreateJob } from 'data-services/hooks/jobs/useCreateJob'
import { PlusIcon } from 'lucide-react'
import { Button, Dialog } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { JobDetailsForm } from './job-details-form/job-details-form'
import { JOB_TYPE_TRAIN_CLASSIFIER } from './job-details-form/types'
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
      <Dialog.Trigger asChild>
        <Button size="small" variant="outline">
          <PlusIcon className="w-4 h-4" />
          <span>{label}</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <Dialog.Header title={label} />
        <div className={styles.content}>
          <JobDetailsForm
            error={error}
            isLoading={isLoading}
            isSuccess={isSuccess}
            onSubmit={({
              algorithmKey,
              jobType,
              minPerSpecies,
              occurrenceSet,
              testFraction,
              ...data
            }) => {
              createJob({
                ...data,
                jobType,
                params:
                  jobType === JOB_TYPE_TRAIN_CLASSIFIER
                    ? {
                        algorithm_key: algorithmKey,
                        occurrence_set_id: occurrenceSet
                          ? Number(occurrenceSet)
                          : undefined,
                        test_fraction: testFraction,
                        min_per_species: minPerSpecies,
                      }
                    : undefined,
                projectId: projectId as string,
              })
            }}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
