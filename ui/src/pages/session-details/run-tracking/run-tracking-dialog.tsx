import { useCreateTrackingJob } from 'data-services/hooks/jobs/useCreateTrackingJob'
import { SessionDetails } from 'data-services/models/session-details'
import { RouteIcon } from 'lucide-react'
import { Button, Dialog } from 'nova-ui-kit'
import { TrackingJobForm } from 'pages/job-details/tracking-job-form/tracking-job-form'
import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { STRING, translate } from 'utils/language'

const CLOSE_TIMEOUT = 1000

export const RunTrackingDialog = ({ session }: { session: SessionDetails }) => {
  const { projectId } = useParams()
  const [isOpen, setIsOpen] = useState(false)
  const { createTrackingJob, isLoading, isSuccess, error } =
    useCreateTrackingJob(() =>
      setTimeout(() => setIsOpen(false), CLOSE_TIMEOUT)
    )
  const label = translate(STRING.TRACKING_JOB_RUN_ON_SESSION)

  return (
    <Dialog.Root open={isOpen} onOpenChange={setIsOpen}>
      <Dialog.Trigger asChild>
        <Button size="small" variant="outline">
          <RouteIcon className="w-4 h-4" />
          <span>{translate(STRING.TRACKING_JOB_RUN)}</span>
        </Button>
      </Dialog.Trigger>
      <Dialog.Content ariaCloselabel={translate(STRING.CLOSE)}>
        <Dialog.Header title={label} />
        <div className="w-[720px] max-w-full">
          <TrackingJobForm
            error={error}
            isLoading={isLoading}
            isSuccess={isSuccess}
            onSubmit={(values) =>
              createTrackingJob({
                ...values,
                projectId: projectId as string,
              })
            }
            scope={{ type: 'session', sessionId: session.id }}
          />
        </div>
      </Dialog.Content>
    </Dialog.Root>
  )
}
