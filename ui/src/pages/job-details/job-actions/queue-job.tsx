import { useQueueJob } from 'data-services/hooks/jobs/useQueueJob'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { CheckIcon, Loader2Icon, PlayIcon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const QueueJob = ({
  compact,
  jobId,
}: {
  compact?: boolean
  jobId: string
}) => {
  const { queueJob, isLoading, isSuccess } = useQueueJob()

  return compact ? (
    <BasicTooltip content={translate(STRING.START)}>
      <Button
        aria-label={translate(STRING.START)}
        disabled={isLoading || isSuccess}
        onClick={() => queueJob(jobId)}
        size="icon"
        variant="ghost"
      >
        {isSuccess ? (
          <CheckIcon className="w-4 h-4" />
        ) : isLoading ? (
          <Loader2Icon className="w-4 h-4 animate-spin" />
        ) : (
          <PlayIcon className="w-4 h-4" />
        )}
      </Button>
    </BasicTooltip>
  ) : (
    <Button
      disabled={isLoading || isSuccess}
      onClick={() => queueJob(jobId)}
      size="small"
      variant="ghost"
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
