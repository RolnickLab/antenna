import { useSyncDeploymentSourceImages } from 'data-services/hooks/deployments/useSyncDeploymentSourceImages'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
import { CheckIcon, EyeIcon, Loader2Icon } from 'lucide-react'
import { Button, buttonVariants } from 'nova-ui-kit'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import styles from './styles.module.scss'

export const SyncDeploymentSourceImages = ({
  deploymentId,
  isConnected,
}: {
  deploymentId: string
  isConnected?: boolean
}) => {
  const { syncDeploymentSourceImages, isLoading, isSuccess, data } =
    useSyncDeploymentSourceImages()

  const projectId = data?.data.project_id
  const jobId = data?.data.job_id

  return (
    <div className={styles.wrapper}>
      <Button
        disabled={!isConnected || isSuccess || isLoading}
        onClick={() => syncDeploymentSourceImages(deploymentId)}
        size="small"
        variant="success"
      >
        <span>Sync now</span>
        {isSuccess ? (
          <CheckIcon className="w-4 h-4" />
        ) : isLoading ? (
          <Loader2Icon className="w-4 h-4 animate-spin" />
        ) : null}
      </Button>
      {projectId && jobId && (
        <BasicTooltip
          asChild
          content={`Job ${jobId} "Sync captures for deployment ${deploymentId}"`}
        >
          <Link
            className={buttonVariants({ size: 'icon', variant: 'ghost' })}
            to={getAppRoute({
              to: APP_ROUTES.JOB_DETAILS({
                projectId: String(projectId),
                jobId: String(jobId),
              }),
              keepSearchParams: true,
            })}
          >
            <EyeIcon className="w-4 h-4" />
          </Link>
        </BasicTooltip>
      )}
    </div>
  )
}
