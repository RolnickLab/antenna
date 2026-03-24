import { useQueueJob } from 'data-services/hooks/jobs/useQueueJob'
import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const QueueJob = ({ jobId }: { jobId: string }) => {
  const { queueJob, isLoading, isSuccess } = useQueueJob()

  return (
    <Button
      disabled={isSuccess}
      onClick={() => queueJob(jobId)}
      size="small"
      variant="outline"
    >
      <span>{translate(STRING.START)}</span>
      {isSuccess ? (
        <CheckIcon className="w-4 h-4" />
      ) : isLoading ? (
        <Loader2Icon className="w-4 h-4 animate-spin" />
      ) : null}
    </Button>
  )
}
