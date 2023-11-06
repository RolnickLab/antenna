import { useJobDetails } from 'data-services/hooks/jobs/useJobDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { JobDetails } from 'pages/job-details/job-details'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'

export const CaptureJobDialog = ({ id }: { id: string }) => {
  const [isOpen, setIsOpen] = useState(false)
  const { job, isLoading, isFetching } = useJobDetails(id)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger>
        <IconButton theme={IconButtonTheme.Neutral} icon={IconType.BatchId} />
      </Dialog.Trigger>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
      >
        {job ? (
          <JobDetails
            job={job}
            title="Job details"
            isFetching={isFetching}
            onDelete={() => setIsOpen(false)}
          />
        ) : null}
      </Dialog.Content>
    </Dialog.Root>
  )
}
