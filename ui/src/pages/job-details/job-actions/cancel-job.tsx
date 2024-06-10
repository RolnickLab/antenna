import { useCancelJob } from 'data-services/hooks/jobs/useCancelJob'
import { Button } from 'design-system/components/button/button'
import { IconType } from 'design-system/components/icon/icon'
import { STRING, translate } from 'utils/language'

export const CancelJob = ({ jobId }: { jobId: string }) => {
  const { cancelJob, isLoading, isSuccess } = useCancelJob()

  if (isSuccess) {
    return (
      <Button label={translate(STRING.CANCEL)} icon={IconType.RadixCheck} />
    )
  }

  return (
    <Button
      label={translate(STRING.CANCEL)}
      loading={isLoading}
      onClick={() => cancelJob(jobId)}
    />
  )
}
