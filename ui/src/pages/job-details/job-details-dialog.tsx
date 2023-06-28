import { Job } from 'data-services/models/job'
import * as Dialog from 'design-system/components/dialog/dialog'
import { useEffect, useState } from 'react'
import { STRING, translate } from 'utils/language'
import { JobDetails } from './job-details'

export const JobDetailsDialog = ({
  job,
  open,
  onOpenChange,
}: {
  job?: Job
  open: boolean
  onOpenChange: (open: boolean) => void
}) => {
  const [isEditing, setIsEditing] = useState(false)

  useEffect(() => {
    // Reset to view mode when a new job is selected
    setIsEditing(false)
  }, [job?.id])

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        {job ? (
          <JobDetails
            job={job}
            title="Job details"
            onCancelClick={() => onOpenChange(false)}
          />
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
