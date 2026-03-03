import { useJobDetails } from 'data-services/hooks/jobs/useJobDetails'
import * as Dialog from 'design-system/components/dialog/dialog'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
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
      <BasicTooltip asChild content="Job details">
        <Dialog.Trigger asChild>
          <Button
            size="icon"
            className="rounded-md !bg-neutral-700 text-neutral-200"
          >
            <EyeIcon className="w-4 h-4" />
          </Button>
        </Dialog.Trigger>
      </BasicTooltip>
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
