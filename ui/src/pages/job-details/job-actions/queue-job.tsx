import { useQueueJob } from 'data-services/hooks/jobs/useQueueJob'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { STRING, translate } from 'utils/language'

export const QueueJob = ({ jobId }: { jobId: string }) => {
  const { queueJob, isLoading, isSuccess } = useQueueJob()

  if (isSuccess) {
    return (
      <Button
        label={translate(STRING.QUEUE)}
        icon={IconType.RadixCheck}
        theme={ButtonTheme.Success}
      />
    )
  }

  return (
    <Button
      label={translate(STRING.QUEUE)}
      loading={isLoading}
      theme={ButtonTheme.Success}
      onClick={() => queueJob(jobId)}
    />
  )
}
