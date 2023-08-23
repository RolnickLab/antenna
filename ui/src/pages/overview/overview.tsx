import { Project } from 'data-services/models/project'
import { Icon, IconTheme, IconType } from 'design-system/components/icon/icon'
import { LoadingSpinner } from 'design-system/components/loading-spinner/loading-spinner'
import { Plot } from 'design-system/components/plot/plot'
import { Error } from 'pages/error/error'
import { useOutletContext } from 'react-router-dom'
import { DeploymentsMap } from './deployments-map/deployments-map'
import styles from './overview.module.scss'

export const Overview = () => {
  const { project, isLoading, error } = useOutletContext<{
    project?: Project
    isLoading: boolean
    isFetching: boolean
    error?: unknown
  }>()

  if (!isLoading && error) {
    return <Error />
  }

  if (isLoading || !project) {
    return (
      <div className={styles.loadingWrapper}>
        <LoadingSpinner />
      </div>
    )
  }

  return (
    <>
      <div className={styles.about}>
        <div className={styles.aboutImage}>
          {project.image ? (
            <img src={project.image} alt="" />
          ) : (
            <Icon
              type={IconType.Photograph}
              theme={IconTheme.Neutral}
              size={32}
            />
          )}
        </div>
        <div className={styles.aboutInfo}>
          <h1 className={styles.title}>{project.name}</h1>
          <p className={styles.description}>{project.description}</p>
          <DeploymentsMap deployments={project.deployments} />
        </div>
      </div>
      <div className={styles.plotsContainer}>
        <div className={styles.plotsContent}>
          <span className={styles.label}>Summary</span>
          <div className={styles.plots}>
            {project.summaryData.map((summary, index) => (
              <Plot
                key={index}
                title={summary.title}
                data={summary.data}
                type={summary.type}
              />
            ))}
          </div>
        </div>
      </div>
    </>
  )
}
