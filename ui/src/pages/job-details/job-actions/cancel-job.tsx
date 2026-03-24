import { useCancelJob } from 'data-services/hooks/jobs/useCancelJob'
import { CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const CancelJob = ({ jobId }: { jobId: string }) => {
  const { cancelJob, isLoading, isSuccess } = useCancelJob()

  return (
    <Button
      disabled={isSuccess}
      onClick={() => cancelJob(jobId)}
      size="small"
      variant="outline"
    >
      <span>{translate(STRING.CANCEL)}</span>
      {isSuccess ? (
        <CheckIcon className="w-4 h-4" />
      ) : isLoading ? (
        <Loader2Icon className="w-4 h-4 animate-spin" />
      ) : null}
    </Button>
  )
}
