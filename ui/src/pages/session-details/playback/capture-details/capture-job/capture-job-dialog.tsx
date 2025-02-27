import { useJobDetails } from 'data-services/hooks/jobs/useJobDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { Tooltip } from 'design-system/components/tooltip/tooltip'
import { EyeIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { JobDetails } from 'pages/job-details/job-details'
import { useState } from 'react'
import { STRING, translate } from 'utils/language'

export const CaptureJobDialog = ({ id }: { id: string }) => {
  const [isOpen, setIsOpen] = useState(false)
  const { job, isLoading, isFetching, error } = useJobDetails(id, isOpen)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Tooltip content="Job details">
        <div>
          <Dialog.Trigger>
            <Button
              size="icon"
              className="w-8 h-8 !bg-neutral-700 text-neutral-200"
            >
              <EyeIcon className="w-4 h-4" />
            </Button>
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
