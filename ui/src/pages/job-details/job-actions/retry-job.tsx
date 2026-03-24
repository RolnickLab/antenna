import { useRetryJob } from 'data-services/hooks/jobs/useRetryJob'
import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const RetryJob = ({ jobId }: { jobId: string }) => {
  const { retryJob, isLoading, isSuccess } = useRetryJob()

  return (
    <Button
      disabled={isSuccess}
      onClick={() => retryJob(jobId)}
      size="small"
      variant="outline"
    >
      <span>{translate(STRING.RETRY)}</span>
      {isSuccess ? (
        <CheckIcon className="w-4 h-4" />
      ) : isLoading ? (
        <Loader2Icon className="w-4 h-4 animate-spin" />
      ) : null}
    </Button>
  )
}
