import { useJobDetails } from 'data-services/hooks/jobs/useJobDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import {
  IconButton,
  IconButtonTheme,
} from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { JobDetails } from 'pages/job-details/job-details'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'

export const CaptureJobDialog = ({ id }: { id: string }) => {
  const [isOpen, setIsOpen] = useState(false)
  const { job, isLoading, isFetching, error } = useJobDetails(id)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Tooltip content={job?.description ?? `Job ${id}`}>
        <div>
          <Dialog.Trigger>
            <IconButton
              theme={IconButtonTheme.Neutral}
              icon={IconType.BatchId}
            />
          </Dialog.Trigger>
        </div>
      </Tooltip>
      <Dialog.Content
        ariaCloselabel={translate(STRING.CLOSE)}
        isLoading={isLoading}
        error={error}
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
