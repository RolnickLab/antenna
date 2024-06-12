import { useSyncDeploymentSourceImages } from 'data-services/hooks/deployments/useSyncDeploymentSourceImages'
import { Button, ButtonTheme } from 'design-system/components/button/button'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { Link } from 'react-router-dom'
import { APP_ROUTES } from 'utils/constants'
import { getAppRoute } from 'utils/getAppRoute'
import { STRING, translate } from 'utils/language'
import styles from './styles.module.scss'

export const SyncDeploymentSourceImages = ({
  deploymentId,
}: {
  deploymentId: string
}) => {
  const { syncDeploymentSourceImages, isLoading, isSuccess, error, data } =
    useSyncDeploymentSourceImages()

  if (isSuccess) {
    const projectId = data?.data.project_id
    const jobId = data?.data.job_id

    return (
      <>
        <div className={styles.buttonWrapper}>
          <Button
            label={translate(STRING.QUEUED)}
            icon={IconType.RadixClock}
            theme={ButtonTheme.Neutral}
            disabled={true}
          />
          {projectId && jobId && (
            <Link
              className={styles.link}
              to={getAppRoute({
                to: APP_ROUTES.JOB_DETAILS({
                  projectId: String(projectId),
                  jobId: String(jobId),
                }),
                keepSearchParams: true,
              })}
            >
              <span>Job details {jobId}</span>
              <Icon type={IconType.ExternalLink} theme={IconTheme.Primary} />
            </Link>
          )}
        </div>
      </>
    )
  }

  if (error) {
    return (
      <Button
        label={translate(STRING.FAILED)}
        icon={IconType.Error}
        theme={ButtonTheme.Error}
      />
    )
  }

  return (
    <Button
      label={translate(STRING.SYNC)}
      loading={isLoading}
      theme={ButtonTheme.Success}
      onClick={() => syncDeploymentSourceImages(deploymentId)}
    />
  )
}
