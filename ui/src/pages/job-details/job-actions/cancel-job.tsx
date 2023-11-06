import { useCancelJob } from 'data-services/hooks/jobs/useCancelJob'
import { Button } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'

export const CancelJob = ({ jobId }: { jobId: string }) => {
  const { cancelJob, isLoading, isSuccess } = useCancelJob()

  if (isSuccess) {
    return <Button label="Cancel job" icon={IconType.RadixCheck} />
  }

  return (
    <Button
      label="Cancel job"
      loading={isLoading}
      onClick={() => cancelJob(jobId)}
    />
  )
}
