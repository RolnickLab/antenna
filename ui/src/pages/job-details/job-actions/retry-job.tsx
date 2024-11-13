import { useRetryJob } from 'data-services/hooks/jobs/useRetryJob'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { STRING, translate } from 'utils/language'

export const RetryJob = ({ jobId }: { jobId: string }) => {
  const { retryJob, isLoading, isSuccess } = useRetryJob()

  if (isSuccess) {
    return (
      <Button
        label={translate(STRING.RETRY)}
        icon={IconType.RadixCheck}
        theme={ButtonTheme.Neutral}
      />
    )
  }

  return (
    <Button
      label={translate(STRING.RETRY)}
      loading={isLoading}
      theme={ButtonTheme.Neutral}
      onClick={() => retryJob(jobId)}
    />
  )
}
