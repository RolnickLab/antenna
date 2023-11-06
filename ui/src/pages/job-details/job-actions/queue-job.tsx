import { useQueueJob } from 'data-services/hooks/jobs/useQueueJob'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'

export const QueueJob = ({ jobId }: { jobId: string }) => {
  const { queueJob, isLoading, isSuccess } = useQueueJob()

  if (isSuccess) {
    return (
      <Button
        label="Queue job"
        icon={IconType.RadixCheck}
        theme={ButtonTheme.Success}
      />
    )
  }

  return (
    <Button
      label="Queue job"
      loading={isLoading}
      theme={ButtonTheme.Success}
      onClick={() => queueJob(jobId)}
    />
  )
}
