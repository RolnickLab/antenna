import { useCancelJob } from 'data-services/hooks/jobs/useCancelJob'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { BanIcon, CheckIcon, Loader2Icon } from 'lucide-react'
import { Button } from 'nova-ui-kit'
import { STRING, translate } from 'utils/language'

export const CancelJob = ({
  compact,
  jobId,
}: {
  compact?: boolean
  jobId: string
}) => {
  const { cancelJob, isLoading, isSuccess } = useCancelJob()

  return compact ? (
    <BasicTooltip content={translate(STRING.CANCEL)}>
      <Button
        aria-label={translate(STRING.CANCEL)}
        disabled={isLoading || isSuccess}
        onClick={() => cancelJob(jobId)}
        size="icon"
        variant="ghost"
      >
        {isSuccess ? (
          <CheckIcon className="w-4 h-4" />
        ) : isLoading ? (
          <Loader2Icon className="w-4 h-4 animate-spin" />
        ) : (
          <BanIcon className="w-4 h-4" />
        )}
      </Button>
    </BasicTooltip>
  ) : (
    <Button
      disabled={isLoading || isSuccess}
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
