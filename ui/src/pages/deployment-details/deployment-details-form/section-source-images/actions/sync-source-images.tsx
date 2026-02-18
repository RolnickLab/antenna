import { useSyncDeploymentSourceImages } from 'data-services/hooks/deployments/useSyncDeploymentSourceImages'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { IconButton } from 'design-system/components/icon-button/icon-button'
import { IconType } from 'design-system/components/icon/icon'
import { BasicTooltip } from 'design-system/components/tooltip/basic-tooltip'
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
        label="Sync now"
        loading={isLoading}
        disabled={!isConnected || isSuccess}
        theme={ButtonTheme.Success}
        icon={isSuccess ? IconType.RadixCheck : undefined}
        onClick={() => syncDeploymentSourceImages(deploymentId)}
      />
      {projectId && jobId && (
        <BasicTooltip
          asChild
          content={`Job ${jobId} "Sync captures for deployment ${deploymentId}"`}
        >
          <Link
            to={getAppRoute({
              to: APP_ROUTES.JOB_DETAILS({
                projectId: String(projectId),
                jobId: String(jobId),
              }),
              keepSearchParams: true,
            })}
          >
            <IconButton icon={IconType.BatchId} />
          </Link>
        </BasicTooltip>
      )}
    </div>
  )
}
