import { FormRow, FormSection } from 'components/form/layout/layout'
import { useCreateJob } from 'data-services/hooks/jobs/useCreateJob'
import { useCreateTrackingJob } from 'data-services/hooks/jobs/useCreateTrackingJob'
import { PlusIcon } from 'lucide-react'
import { Button, Dialog, InputContent, Select } from 'nova-ui-kit'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'
import { useCanStartTracking } from 'utils/project-features/useProjectFeature'
import { JobDetailsForm } from './job-details-form/job-details-form'
import styles from './job-details.module.scss'
import { TrackingJobForm } from './tracking-job-form/tracking-job-form'

const CLOSE_TIMEOUT = 1000

type NewJobType = 'processing' | 'tracking'

export const NewJobDialog = () => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const [jobType, setJobType] = useState<NewJobType>('processing')
  const canStartTracking = useCanStartTracking()
  const closeLater = () =>
    setTimeout(() => {
      setIsOpen(false)
    }, CLOSE_TIMEOUT)
  const { createJob, isLoading, isSuccess, error } = useCreateJob(closeLater)
  const tracking = useCreateTrackingJob(closeLater)

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
          {canStartTracking ? (
            <FormSection>
              <FormRow>
                <InputContent label={translate(STRING.TRACKING_JOB_TYPE)}>
                  <Select.Root
                    onValueChange={(value) => setJobType(value as NewJobType)}
                    value={jobType}
                  >
                    <Select.Trigger>
                      <Select.Value />
                    </Select.Trigger>
                    <Select.Content>
                      <Select.Item value="processing">
                        {translate(STRING.TRACKING_JOB_TYPE_PROCESSING)}
                      </Select.Item>
                      <Select.Item value="tracking">
                        {translate(STRING.TRACKING_JOB_TYPE_TRACKING)}
                      </Select.Item>
                    </Select.Content>
                  </Select.Root>
                </InputContent>
              </FormRow>
            </FormSection>
          ) : null}
          {canStartTracking && jobType === 'tracking' ? (
            <TrackingJobForm
              error={tracking.error}
              isLoading={tracking.isLoading}
              isSuccess={tracking.isSuccess}
              onSubmit={(values) =>
                tracking.createTrackingJob({
                  ...values,
                  projectId: projectId as string,
                })
              }
            />
          ) : (
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
          )}
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
